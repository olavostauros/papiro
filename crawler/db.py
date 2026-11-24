"""Postgres query store — schema + idempotent shard→DB sync.

The shards in ``data/questions/<EVENTO>.json`` remain the transport/backup
format (see ``crawler/shards.py``); this module is the normalized store the
API queries. The schema mirrors the flat ``Questao`` record
(``crawler/models.py``) with the interned shard dimensions promoted to
global tables:

    banca ─┐
           ├─ evento ── prova ──┐
    orgao ─┴─ cargo ────────────┼─ questao
    assunto ────────────────────┘

Decisions (see .agents/docs/docker-postgres.md):

- Identity = ``questao.id`` (text PK, ``cebraspe-2024-pf-escrivao-042``) —
  the same dedup criterion as ``assemble``: existing ids are skipped.
- ``cargo`` is the pair (orgao, nome) — "Analista Judiciário" at TRT8 is a
  different row than at TRF6.
- ``assunto_id`` NULL = sem assunto (shard interned ""→NULL).
- ``alternativas`` NULL = ``["Certo", "Errado"]`` — the same omission the
  shard format uses (``[]`` is stored as-is: a MC item with no extracted
  alternatives is not a C/E item).

The sync is dialect-agnostic (select-then-insert per batch), so it runs
against Postgres in production and SQLite in tests:

    .venv/bin/python -m crawler.db sync                 # DATABASE_URL or default
    .venv/bin/python -m crawler.db sync --url sqlite:////tmp/papiro.db
    .venv/bin/python -m crawler.db stats --url ...
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import (JSON, CheckConstraint, ForeignKey, Index, Integer,
                        SmallInteger, Text, UniqueConstraint, create_engine,
                        delete, event, func, insert, select, text, update)
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .shards import CERTO_ERRADO, SHARD_DIR, evento_key, load_shard_records

DEFAULT_URL = "postgresql+psycopg://papiro:papiro@localhost:5432/papiro"
BATCH = 1000


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class Banca(Base):
    __tablename__ = "banca"
    # smallserial no Postgres; SQLite só autoincrementa INTEGER PK
    id: Mapped[int] = mapped_column(
        SmallInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    nome: Mapped[str] = mapped_column(Text, unique=True, nullable=False)


class Orgao(Base):
    __tablename__ = "orgao"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(Text, unique=True, nullable=False)


class Assunto(Base):
    __tablename__ = "assunto"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(Text, unique=True, nullable=False)


class Evento(Base):
    __tablename__ = "evento"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evento: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    banca_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("banca.id"), nullable=False)


class Prova(Base):
    __tablename__ = "prova"
    __table_args__ = (UniqueConstraint("evento_id", "fonte"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evento_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evento.id"), nullable=False)
    fonte: Mapped[str] = mapped_column(Text, nullable=False)


class Cargo(Base):
    __tablename__ = "cargo"
    __table_args__ = (UniqueConstraint("orgao_id", "nome"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    orgao_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orgao.id"), nullable=False)
    nome: Mapped[str] = mapped_column(Text, nullable=False)


class QuestaoDB(Base):
    __tablename__ = "questao"
    __table_args__ = (
        CheckConstraint("tipo IN ('certo_errado','multipla_escolha')"),
        CheckConstraint("gabarito IN ('certo','errado','a','b','c','d','e')"),
        Index("questao_filtros", "cargo_id", "ano"),
        Index("questao_ano", "ano"),
        Index("questao_prova", "prova_id"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    prova_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("prova.id"), nullable=False)
    cargo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cargo.id"), nullable=False)
    assunto_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("assunto.id"))
    ano: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    alternativas: Mapped[Optional[list]] = mapped_column(
        postgresql.JSONB().with_variant(JSON(), "sqlite"))
    gabarito: Mapped[str] = mapped_column(Text, nullable=False)


# partial index (assunto_id IS NOT NULL) — declared outside __table_args__
# because the WHERE clause needs the table object to exist first
Index("questao_assunto", QuestaoDB.assunto_id,
      postgresql_where=QuestaoDB.assunto_id.isnot(None))


# ---------------------------------------------------------------------------
# Engine / session
# ---------------------------------------------------------------------------

def unaccent_str(s: Optional[str]) -> Optional[str]:
    """Strip diacritics — mirrors the SQL ``unaccent()`` used by ?q= filters."""
    if s is None:
        return None
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Normalização de nomes de dimensão (display)
#
# Shards guardam o texto cru da banca; ~10% dos orgao/cargo chegam ALL-CAPS.
# O DB é o store curado que a API serve — normaliza ao internar a dimensão.
# Regras: conectivos minúsculos, siglas preservadas (sem vogal, ≤2 letras ou
# na lista), demais palavras capitalizadas.
# ---------------------------------------------------------------------------

_VOGAL = re.compile(r"[AEIOUÁÉÍÓÚÂÊÎÔÛÃÕÀÄËÏÖÜ]")
_PIECE = re.compile(r"^(\W*)(\w*)(\W*)$")

_CONECTIVOS = frozenset("""
    a o as os um uma uns umas e de da do das dos em no na nos nas
    num numa nuns numas para por pelo pela pelos pelas com sem sob sobre
    ao aos à às
""".split())

# Siglas com vogal que a regra "sem vogal" não captura — mantidas maiúsculas.
_SIGLAS = frozenset("""
    ABIN AGU ANAC ANATEL ANEEL ANM ANP ANS ANSA ANTAQ ANTT ANVISA APEX
    BANESE BANRISUL BCB BDMG BNDES CAGEPA CAESB CAPES CAU CBM CGU CNPJ
    CNPQ COREN CRESS CVM DEPEN DETRAN DNIT DPE DPU EEAR EFOMM EMBRAPA
    EMPREL ESA EXE FAB FNDE FUNAI FUNPRESP IBAMA IBGE IML INPI INSA INSS IPEA
    ITA MCTI MEC MMA OAB PGE PGFN PGU PREVIC SEBRAE SEFAZ SEFIN SEPLAG
    SENAC SENAI SENAT SERPRO SESI SESC SEST SUSEP UDESC UEM UEPG UNB
    UNESP UNICAMP UNIFESP UNIVESP URCA UVA
""".split())


def _norm_piece(piece: str, first: bool) -> str:
    m = _PIECE.match(piece)
    if not m or not m.group(2):
        return piece
    pre, core, suf = m.groups()
    if not first and core.lower() in _CONECTIVOS:
        return pre + core.lower() + suf
    if (not core.isalpha() or core in _SIGLAS
            or not _VOGAL.search(core) or len(core) <= 2):
        return piece
    return pre + core.capitalize() + suf


def _norm_token(token: str, first: bool) -> str:
    parts = re.split(r"([-/])", token)
    return "".join(
        p if p in "-/" else _norm_piece(p, first and i == 0)
        for i, p in enumerate(parts))


def normalize_nome(nome: str) -> str:
    """Title-case de nome ALL-CAPS (orgao/cargo) para exibição.

    Nomes com qualquer letra minúscula são retornados intactos — só o
    dataset gritado é tocado. Token único curto é tratado como sigla.
    ('ª'/'º' contam como neutros — isupper() falharia em "8ª REGIÃO".)
    """
    if not nome or nome != nome.upper() or nome.upper() == nome.lower():
        return nome
    tokens = nome.split()
    if len(tokens) == 1 and len(tokens[0]) <= 10:
        return nome
    return " ".join(_norm_token(t, i == 0) for i, t in enumerate(tokens))


def get_engine(url: Optional[str] = None, **kw) -> Engine:
    """Engine for DATABASE_URL (env), explicit url, or the local default.

    Plain ``postgresql://`` URLs are coerced to the psycopg 3 driver.
    SQLite engines get a ``unaccent()`` SQL function so accent-insensitive
    search behaves like on Postgres (contrib extension).
    """
    url = url or os.environ.get("DATABASE_URL") or DEFAULT_URL
    if url.startswith(("postgresql://", "postgres://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    kw.setdefault("pool_pre_ping", True)
    engine = create_engine(url, **kw)
    if engine.url.get_backend_name() == "sqlite":
        event.listen(engine, "connect",
                     lambda conn, _: conn.create_function(
                         "unaccent", 1, unaccent_str))
    return engine


def create_schema(engine: Engine) -> None:
    if engine.url.get_backend_name() == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
    Base.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Sync shard → banco
# ---------------------------------------------------------------------------

@dataclass
class SyncStats:
    eventos: int = 0
    records: int = 0
    inserted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _get_or_create(session: Session, cache: dict, key, model, **kw) -> int:
    """SELECT id by natural key; INSERT on miss. Returns the pk."""
    if key in cache:
        return cache[key]
    stmt = select(model.id)
    for col, val in kw.items():
        stmt = stmt.where(getattr(model, col) == val)
    pk = session.scalar(stmt)
    if pk is None:
        inst = model(**kw)
        session.add(inst)
        session.flush()
        pk = inst.id
    cache[key] = pk
    return pk


def _group_by_evento(records: Iterable[dict], evento: Optional[str]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for r in records:
        ev = evento or evento_key(r["fonte"], r)
        groups.setdefault(ev, []).append(r)
    return groups


def sync_records(records: Iterable[dict], engine: Engine, *,
                 evento: Optional[str] = None,
                 stats: Optional[SyncStats] = None) -> SyncStats:
    """Upsert flat ``Questao`` records (shard_to_records/model_dump shape).

    Idempotent: existing ``questao.id`` rows are skipped (same criterion as
    ``assemble``). One transaction per evento group.
    """
    stats = stats or SyncStats()
    # global dimension caches — shared across eventos within the call
    bancas: dict[str, int] = {}
    orgaos: dict[str, int] = {}
    assuntos: dict[str, int] = {}
    cargos: dict[tuple[int, str], int] = {}

    for ev, recs in _group_by_evento(records, evento).items():
        stats.eventos += 1
        stats.records += len(recs)
        with Session(engine) as session:
            banca_id = _get_or_create(session, bancas, recs[0]["banca"],
                                      Banca, nome=recs[0]["banca"])
            evento_id = _get_or_create(session, {}, ev, Evento,
                                       evento=ev, banca_id=banca_id)

            prova_ids: dict[str, int] = {}
            for fonte in {r["fonte"] for r in recs}:
                prova_ids[fonte] = _get_or_create(
                    session, {}, (evento_id, fonte), Prova,
                    evento_id=evento_id, fonte=fonte)

            def cargo_id(r: dict) -> int:
                orgao = normalize_nome(r["orgao"])
                cargo = normalize_nome(r["cargo"])
                oid = _get_or_create(session, orgaos, orgao,
                                     Orgao, nome=orgao)
                return _get_or_create(session, cargos, (oid, cargo),
                                      Cargo, orgao_id=oid, nome=cargo)

            def assunto_id(r: dict) -> Optional[int]:
                if not r["assunto"]:
                    return None
                return _get_or_create(session, assuntos, r["assunto"],
                                      Assunto, nome=r["assunto"])

            for i in range(0, len(recs), BATCH):
                chunk = recs[i:i + BATCH]
                ids = [r["id"] for r in chunk]
                existing = set(session.scalars(
                    select(QuestaoDB.id).where(QuestaoDB.id.in_(ids))))
                rows = [{
                    "id": r["id"],
                    "prova_id": prova_ids[r["fonte"]],
                    "cargo_id": cargo_id(r),
                    "assunto_id": assunto_id(r),
                    "ano": r["ano"],
                    "tipo": r["tipo"],
                    "enunciado": r["enunciado"],
                    "alternativas": (None if r["alternativas"] == CERTO_ERRADO
                                     else r["alternativas"]),
                    "gabarito": r["gabarito"],
                } for r in chunk if r["id"] not in existing]
                if rows:
                    session.execute(insert(QuestaoDB), rows)
                stats.inserted += len(rows)
                stats.skipped += len(chunk) - len(rows)
            session.commit()
    return stats


def sync_shard(path: Path, engine: Engine, *,
               stats: Optional[SyncStats] = None) -> SyncStats:
    """Sync one ``data/questions/<EVENTO>.json`` file."""
    return sync_records(load_shard_records(path), engine,
                        evento=path.stem, stats=stats)


def sync_all(engine: Engine, shard_dir: Path = SHARD_DIR) -> SyncStats:
    """Sync every shard under ``shard_dir`` (idempotent, resumable)."""
    stats = SyncStats()
    for path in sorted(shard_dir.glob("*.json")):
        before = stats.inserted
        try:
            sync_shard(path, engine, stats=stats)
        except Exception as exc:  # keep going; report at the end
            sessionless = f"{path.name}: {exc}"
            stats.errors.append(sessionless)
            print(f"!! {sessionless}", file=sys.stderr)
        else:
            print(f"{path.name}: +{stats.inserted - before}")
    return stats


# ---------------------------------------------------------------------------
# Normalização retroativa
# ---------------------------------------------------------------------------

def normalize_dims(engine: Engine,
                   renames: Optional[dict[str, str]] = None) -> dict[str, int]:
    """Renomeia dimensões existentes para exibição.

    ``renames`` (nome bruto → nome alvo) cobre valores inválidos que o
    title-case não adivinha — slugs de evento internados como órgão ou
    cargo trocado na curadoria.
    O restante passa por ``normalize_nome``. Renomear na linha basta
    quando o alvo não existe; colisão com uma dimensão já no destino
    mescla — reponta dependentes e remove a dupla. Retorna contagens.
    """
    renames = renames or {}
    moved = {"orgao": 0, "cargo": 0}
    with Session(engine) as s:
        orgaos = s.execute(select(Orgao.id, Orgao.nome)).all()
        id_por_nome: dict[str, int] = {nome: oid for oid, nome in orgaos}
        for oid, nome in orgaos:
            new = renames.get(nome, normalize_nome(nome))
            if new == nome:
                continue
            if keep := id_por_nome.get(new):
                s.execute(update(Cargo).where(Cargo.orgao_id == oid)
                          .values(orgao_id=keep))
                s.execute(delete(Orgao).where(Orgao.id == oid))
            else:
                s.execute(update(Orgao).where(Orgao.id == oid)
                          .values(nome=new))
                id_por_nome[new] = oid
            moved["orgao"] += 1

        cargos = s.execute(select(Cargo.id, Cargo.orgao_id, Cargo.nome)).all()
        id_por_key = {(oid, nome): cid for cid, oid, nome in cargos}
        for cid, oid, nome in cargos:
            new = renames.get(nome, normalize_nome(nome))
            if new == nome:
                continue
            if keep := id_por_key.get((oid, new)):
                s.execute(update(QuestaoDB)
                          .where(QuestaoDB.cargo_id == cid)
                          .values(cargo_id=keep))
                s.execute(delete(Cargo).where(Cargo.id == cid))
            else:
                s.execute(update(Cargo).where(Cargo.id == cid)
                          .values(nome=new))
                id_por_key[(oid, new)] = cid
            moved["cargo"] += 1
        s.commit()
    return moved


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_sync(args) -> int:
    engine = get_engine(args.url)
    create_schema(engine)
    stats = sync_all(engine, Path(args.shard_dir))
    print(f"\nsync: {stats.eventos} eventos, {stats.records} records, "
          f"{stats.inserted} inseridos, {stats.skipped} já existentes"
          + (f", {len(stats.errors)} erros" if stats.errors else ""))
    return 1 if stats.errors else 0


def _cmd_stats(args) -> int:
    engine = get_engine(args.url)
    with Session(engine) as s:
        for model in (Banca, Orgao, Cargo, Assunto, Evento, Prova, QuestaoDB):
            n = s.scalar(select(func.count()).select_from(model))
            print(f"{model.__tablename__:10} {n}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m crawler.db")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--url", help="DATABASE_URL (default: env ou localhost)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sync", parents=[common],
                       help="cria o schema e sincroniza os shards")
    p.add_argument("--shard-dir", default=str(SHARD_DIR))
    p.set_defaults(fn=_cmd_sync)
    p = sub.add_parser("init", parents=[common], help="só cria o schema")
    p.set_defaults(fn=lambda a: (create_schema(get_engine(a.url)), 0)[1])
    p = sub.add_parser("normalize", parents=[common],
                       help="renomeia dimensões ALL-CAPS existentes")
    p.set_defaults(fn=lambda a: (
        print("normalize:", (m := normalize_dims(get_engine(a.url))),
              "dimensões"), 0)[1])
    p = sub.add_parser("stats", parents=[common], help="contagens por tabela")
    p.set_defaults(fn=_cmd_stats)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
