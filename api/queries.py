"""Query helpers for the papiro API.

The API serves the flat ``Questao`` record (``crawler/models.py`` — the same
shape ``shard_to_records`` emits and ``web/src/data/questions.ts`` types) by
joining the normalized schema in ``crawler/db.py``.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from crawler.db import (Assunto, Banca, Cargo, Evento, Orgao, Prova,
                        QuestaoDB, Texto, unaccent_str)
from crawler.shards import CERTO_ERRADO

TIPOS = ("certo_errado", "multipla_escolha")

# Sonda feita por api.main.create_app: False se o banco não tem unaccent()
# (Postgres sem a extensão) — os filtros q= degradam para ILIKE acentuado.
USE_UNACCENT = True


def base_questao(with_texto: bool = False) -> Select:
    """questao joined out to every dimension — yields flat-record columns.

    ``with_texto`` acrescenta o texto-base (ref/conteudo/citacao/imagem) —
    usado no detalhe e no agente; a listagem também o traz (o card exibe o
    texto em <details>).
    """
    cols = [
        QuestaoDB.id,
        Banca.nome.label("banca"),
        Orgao.nome.label("orgao"),
        Cargo.nome.label("cargo"),
        QuestaoDB.ano,
        Assunto.nome.label("assunto"),
        QuestaoDB.tipo,
        QuestaoDB.enunciado,
        QuestaoDB.alternativas,
        QuestaoDB.gabarito,
        Prova.fonte,
    ]
    stmt = (
        select(*cols)
        .select_from(QuestaoDB)
        .join(Prova, QuestaoDB.prova_id == Prova.id)
        .join(Evento, Prova.evento_id == Evento.id)
        .join(Banca, Evento.banca_id == Banca.id)
        .join(Cargo, QuestaoDB.cargo_id == Cargo.id)
        .join(Orgao, Cargo.orgao_id == Orgao.id)
        .outerjoin(Assunto, QuestaoDB.assunto_id == Assunto.id)
    )
    if with_texto:
        stmt = stmt.add_columns(
            Texto.ref.label("texto_ref"),
            Texto.conteudo.label("texto_conteudo"),
            Texto.citacao.label("texto_citacao"),
            Texto.imagem.label("texto_imagem"),
        ).outerjoin(Texto, QuestaoDB.texto_id == Texto.id)
    return stmt


def _escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def unaccent_ilike(column, q: str):
    """``ILIKE %q%`` insensível a acentos — 'escrivao' casa 'Escrivão'.

    Normaliza o termo em Python e a coluna via ``unaccent()`` quando a
    função existe no banco (USE_UNACCENT); senão, ILIKE direto.
    """
    term = _escape_like(unaccent_str(q) if USE_UNACCENT else q)
    col = func.unaccent(column) if USE_UNACCENT else column
    return col.ilike(f"%{term}%", escape="\\")


def apply_filters(
    stmt: Select,
    *,
    banca: Optional[str] = None,
    orgao: Optional[str] = None,
    cargo: Optional[str] = None,
    ano: Optional[int] = None,
    assunto: Optional[str] = None,
    tipo: Optional[str] = None,
    q: Optional[str] = None,
    evento: Optional[str] = None,
    fonte: Optional[str] = None,
    exclude: Optional[str] = None,
) -> Select:
    """WHERE clauses shared by /questoes and the /filtros cascade.

    ``exclude`` omits one dimension's own filter so its option list is not
    narrowed by itself (standard faceted-select behaviour).
    """
    f = {"banca": banca, "orgao": orgao, "cargo": cargo, "ano": ano,
         "assunto": assunto, "tipo": tipo, "q": q, "evento": evento,
         "fonte": fonte}
    if exclude:
        f[exclude] = None
    if f["banca"]:
        stmt = stmt.where(Banca.nome == f["banca"])
    if f["orgao"]:
        stmt = stmt.where(Orgao.nome == f["orgao"])
    if f["cargo"]:
        stmt = stmt.where(Cargo.nome == f["cargo"])
    if f["ano"]:
        stmt = stmt.where(QuestaoDB.ano == f["ano"])
    if f["assunto"]:
        stmt = stmt.where(Assunto.nome == f["assunto"])
    if f["tipo"] in TIPOS:
        stmt = stmt.where(QuestaoDB.tipo == f["tipo"])
    if f["evento"]:
        stmt = stmt.where(Evento.evento == f["evento"])
    if f["fonte"]:
        stmt = stmt.where(Prova.fonte == f["fonte"])
    if f["q"]:
        stmt = stmt.where(unaccent_ilike(QuestaoDB.enunciado, f["q"]))
    return stmt


def row_to_questao(row) -> dict:
    """Join row → flat ``Questao`` dict. NULLs map back to shard defaults."""
    texto = None
    if getattr(row, "texto_ref", None) is not None or \
            getattr(row, "texto_conteudo", None) is not None or \
            getattr(row, "texto_imagem", None):
        texto = {
            "ref": row.texto_ref or "",
            "conteudo": row.texto_conteudo or "",
            "citacao": row.texto_citacao or "",
            "imagem": bool(row.texto_imagem),
        }
    return {
        "id": row.id,
        "banca": row.banca,
        "orgao": row.orgao,
        "cargo": row.cargo,
        "ano": row.ano,
        "assunto": row.assunto or "",
        "tipo": row.tipo,
        "enunciado": row.enunciado,
        # NULL = ["Certo", "Errado"]; [] stays [] (MC sem alternativas)
        "alternativas": (CERTO_ERRADO if row.alternativas is None
                         else row.alternativas),
        "gabarito": row.gabarito,
        "fonte": row.fonte,
        "texto": texto,
    }


def distinct_values(session: Session, column, *, exclude: str, **filters) -> list:
    """DISTINCT values of a dimension column under the other active filters."""
    stmt = apply_filters(select(column).distinct().select_from(QuestaoDB)
                         .join(Prova, QuestaoDB.prova_id == Prova.id)
                         .join(Evento, Prova.evento_id == Evento.id)
                         .join(Banca, Evento.banca_id == Banca.id)
                         .join(Cargo, QuestaoDB.cargo_id == Cargo.id)
                         .join(Orgao, Cargo.orgao_id == Orgao.id)
                         .outerjoin(Assunto, QuestaoDB.assunto_id == Assunto.id),
                         exclude=exclude, **filters)
    return [v for v in session.scalars(stmt) if v is not None]
