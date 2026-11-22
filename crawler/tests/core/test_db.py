"""crawler.db — schema + sync shard→banco (SQLite como backend de teste)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crawler import db
from crawler.db import (Assunto, Cargo, Evento, Orgao, Prova, QuestaoDB,
                        sync_records, sync_shard)
from crawler.shards import write_shard

pytestmark = pytest.mark.skipif(
    __import__("importlib").util.find_spec("sqlalchemy") is None,
    reason="sqlalchemy não instalado",
)


def rec(qid, **kw):
    base = dict(
        id=qid, banca="Cebraspe", orgao="Polícia Federal",
        cargo="Escrivão de Polícia Federal", ano=2024, assunto="",
        tipo="certo_errado", enunciado=f"enunciado {qid}",
        alternativas=["Certo", "Errado"], gabarito="certo",
        fonte="https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p1.pdf")
    base.update(kw)
    return base


@pytest.fixture
def engine(tmp_path):
    e = db.get_engine(f"sqlite:///{tmp_path / 't.db'}")
    db.create_schema(e)
    return e


def count(engine, model):
    with Session(engine) as s:
        return s.scalar(select(func.count()).select_from(model))


def test_sync_insere_registros_e_dimensoes(engine):
    st = sync_records([rec(f"cebraspe-2024-pf-escrivao-{n:03d}") for n in (1, 2)],
                      engine)
    assert st.inserted == 2 and st.skipped == 0
    assert count(engine, QuestaoDB) == 2
    assert count(engine, Prova) == 1
    assert count(engine, Evento) == 1
    assert count(engine, Cargo) == 1
    assert count(engine, Orgao) == 1
    assert count(engine, Assunto) == 0        # "" vira NULL, não linha


def test_sync_idempotente(engine):
    recs = [rec("cebraspe-2024-pf-escrivao-001")]
    sync_records(recs, engine)
    st = sync_records(recs, engine)
    assert st.inserted == 0 and st.skipped == 1
    assert count(engine, QuestaoDB) == 1


def test_cargo_e_par_orgao_nome(engine):
    sync_records([
        rec("cebraspe-2024-pf-a-001", cargo="Analista", orgao="PF"),
        rec("cebraspe-2024-prf-a-001", cargo="Analista", orgao="PRF"),
    ], engine)
    assert count(engine, Cargo) == 2          # mesmo nome, órgãos distintos


def test_assunto_e_alternativas_mapeiam_shard(engine):
    sync_records([
        rec("cebraspe-2024-pf-a-001", assunto="Direito Penal"),
        rec("cebraspe-2024-pf-a-002", assunto=""),
        rec("cebraspe-2024-pf-a-003", tipo="multipla_escolha",
            alternativas=["A", "B", "C", "D", "E"], gabarito="a"),
        rec("cebraspe-2024-pf-a-004", tipo="multipla_escolha",
            alternativas=[], gabarito="c"),
    ], engine)
    with Session(engine) as s:
        rows = {r.id: r for r in s.scalars(select(QuestaoDB))}
    assert rows["cebraspe-2024-pf-a-001"].assunto_id is not None
    assert rows["cebraspe-2024-pf-a-002"].assunto_id is None
    # ["Certo","Errado"] → NULL (omissão do shard); [] MC permanece []
    assert rows["cebraspe-2024-pf-a-001"].alternativas is None
    assert rows["cebraspe-2024-pf-a-003"].alternativas == ["A", "B", "C", "D", "E"]
    assert rows["cebraspe-2024-pf-a-004"].alternativas == []
    assert count(engine, Assunto) == 1


def test_evento_derivado_da_fonte(engine):
    sync_records([
        rec("cebraspe-2024-pf-a-001",
            fonte="https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p1.pdf"),
        rec("cebraspe-2025-pf-a-001", ano=2025,
            fonte="https://cdn.cebraspe.org.br/concursos/PF_25/arquivos/p1.pdf"),
    ], engine)
    assert count(engine, Evento) == 2
    assert count(engine, Prova) == 2


def test_sync_shard_roundtrip(engine, tmp_path):
    shard_dir = tmp_path / "shards"
    write_shard("PF_24", [rec("cebraspe-2024-pf-escrivao-001")], shard_dir)
    st = sync_shard(shard_dir / "PF_24.json", engine)
    assert st.inserted == 1
    with Session(engine) as s:
        ev = s.scalar(select(Evento.evento))
        assert ev == "PF_24"


def test_get_engine_coage_driver_postgres(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    e = db.get_engine()
    assert e.url.drivername == "postgresql+psycopg"
