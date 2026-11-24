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


def test_normalize_nome():
    n = db.normalize_nome
    # ALL-CAPS → title-case com conectivos minúsculos e siglas preservadas
    assert n("MINISTÉRIO DA EDUCAÇÃO") == "Ministério da Educação"
    assert n("AGENTE DE SUPORTE AO NEGÓCIO") == "Agente de Suporte ao Negócio"
    assert n("ADVOCACIA-GERAL DA UNIÃO") == "Advocacia-Geral da União"
    assert n("SECRETARIA MUNICIPAL DAS FINANÇAS (SEFIN)") == \
        "Secretaria Municipal das Finanças (SEFIN)"
    assert n("TRIBUNAL REGIONAL DO TRABALHO – TRT 8ª REGIÃO") == \
        "Tribunal Regional do Trabalho – TRT 8ª Região"
    assert n("PGE-ES") == "PGE-ES"
    # token único curto = sigla; misto já curado não é tocado
    assert n("ANVISA") == "ANVISA"
    assert n("Polícia Federal") == "Polícia Federal"


def test_sync_normaliza_dimensoes_allcaps(engine):
    sync_records([
        rec("cebraspe-2024-agu-a-001", orgao="ADVOCACIA-GERAL DA UNIÃO",
            cargo="ADVOGADO DA UNIÃO"),
    ], engine)
    with Session(engine) as s:
        assert s.scalar(select(Orgao.nome)) == "Advocacia-Geral da União"
        assert s.scalar(select(Cargo.nome)) == "Advogado da União"


def test_normalize_dims_renomeia_e_mescla(engine):
    # seed legado sem normalização (simula DB pré-normalizador)
    with Session(engine) as s:
        agu = Orgao(nome="ADVOCACIA-GERAL DA UNIÃO")
        fnde_x = Orgao(nome="FNDE_23_ESPECIALISTA")
        fnde = Orgao(nome="FNDE")
        s.add_all([agu, fnde_x, fnde])
        s.flush()
        c1 = Cargo(orgao_id=agu.id, nome="ADVOGADO DA UNIÃO")
        c2 = Cargo(orgao_id=fnde_x.id, nome="ESPECIALISTA")
        c3 = Cargo(orgao_id=fnde.id, nome="Especialista")
        s.add_all([c1, c2, c3])
        s.flush()
        c3_id = c3.id
        s.add_all([
            QuestaoDB(id="q1", prova_id=0, cargo_id=c1.id, ano=2024,
                      tipo="certo_errado", enunciado="e",
                      gabarito="certo"),
            QuestaoDB(id="q2", prova_id=0, cargo_id=c2.id, ano=2024,
                      tipo="certo_errado", enunciado="e",
                      gabarito="certo"),
        ])
        s.commit()
    moved = db.normalize_dims(
        engine, renames={"FNDE_23_ESPECIALISTA": "FNDE"})
    assert moved == {"orgao": 2, "cargo": 2}
    with Session(engine) as s:
        nomes = set(s.scalars(select(Orgao.nome)))
        assert nomes == {"Advocacia-Geral da União", "FNDE"}
        cargos = {(c.orgao_id, c.nome) for c in s.scalars(select(Cargo))}
        assert len(cargos) == 2           # ESPECIALISTA fundiu em Especialista
        q2 = s.scalar(select(QuestaoDB).where(QuestaoDB.id == "q2"))
        assert q2.cargo_id == c3_id       # repontada, não duplicada
