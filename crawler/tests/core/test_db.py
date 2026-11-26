"""crawler.db — schema + sync shard→banco (SQLite como backend de teste)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crawler import db
from crawler.db import (Assunto, Cargo, Evento, Orgao, Prova, QuestaoDB,
                        Texto, prune_event, sync_records, sync_shard)
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
    assert st.inserted == 0 and st.updated == 0 and st.skipped == 1
    assert count(engine, QuestaoDB) == 1


def test_sync_atualiza_proveniencia_e_campos_mutaveis(engine):
    qid = "cebraspe-2024-pf-escrivao-001"
    sync_records([rec(qid, gabarito="certo")], engine)
    fonte2 = "https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p2.pdf"
    st = sync_records([
        rec(qid, fonte=fonte2, gabarito="errado", enunciado="corrigido")
    ], engine)
    assert st.inserted == 0 and st.updated == 1 and st.skipped == 0
    with Session(engine) as s:
        q = s.scalar(select(QuestaoDB).where(QuestaoDB.id == qid))
        fonte = s.scalar(select(Prova.fonte).where(Prova.id == q.prova_id))
    assert fonte == fonte2
    assert q.gabarito == "errado" and q.enunciado == "corrigido"
    assert count(engine, Prova) == 2


def test_sync_shard_prune_remove_ausentes_e_prova_vazia(engine, tmp_path):
    q1 = rec("cebraspe-2024-pf-escrivao-001")
    q2 = rec("cebraspe-2024-pf-escrivao-002")
    sync_records([q1, q2], engine)
    shard_dir = tmp_path / "shards"
    fonte2 = "https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p2.pdf"
    write_shard("PF_24", [rec(q1["id"], fonte=fonte2)], shard_dir)
    st = sync_shard(shard_dir / "PF_24.json", engine, prune=True)
    assert st.updated == 1 and st.deleted == 1
    assert count(engine, QuestaoDB) == 1
    assert count(engine, Prova) == 1
    with Session(engine) as s:
        assert s.scalar(select(Prova.fonte)) == fonte2
        assert s.scalar(select(QuestaoDB.id)) == q1["id"]


def test_sync_atualiza_alternativas_json_null_nas_duas_direcoes(engine):
    qid = "cebraspe-2024-pf-escrivao-001"
    sync_records([rec(qid)], engine)
    st = sync_records([
        rec(qid, tipo="multipla_escolha", alternativas=["A", "B", "C"],
            gabarito="a")
    ], engine)
    assert st.updated == 1
    with Session(engine) as s:
        q = s.scalar(select(QuestaoDB).where(QuestaoDB.id == qid))
        assert q.alternativas == ["A", "B", "C"]
    st = sync_records([rec(qid)], engine)
    assert st.updated == 1
    with Session(engine) as s:
        q = s.scalar(select(QuestaoDB).where(QuestaoDB.id == qid))
        assert q.alternativas is None


def test_prune_remove_textos_orfaos_com_prova_vazia(engine, tmp_path):
    texto = {"ref": "T1", "conteudo": "texto-base", "citacao": "",
             "imagem": False}
    q1 = rec("cebraspe-2024-pf-escrivao-001", texto=texto)
    q2 = rec("cebraspe-2024-pf-escrivao-002")
    sync_records([q1, q2], engine)
    assert count(engine, Texto) == 1
    shard_dir = tmp_path / "shards"
    fonte2 = "https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p2.pdf"
    write_shard("PF_24", [rec(q1["id"], fonte=fonte2, texto=texto)], shard_dir)
    st = sync_shard(shard_dir / "PF_24.json", engine, prune=True)
    assert st.updated == 1 and st.deleted == 1
    assert count(engine, QuestaoDB) == 1
    assert count(engine, Prova) == 1
    assert count(engine, Texto) == 1
    with Session(engine) as s:
        q = s.scalar(select(QuestaoDB).where(QuestaoDB.id == q1["id"]))
        t = s.scalar(select(Texto).where(Texto.id == q.texto_id))
        p = s.scalar(select(Prova).where(Prova.id == t.prova_id))
        assert p.fonte == fonte2


def test_sync_shard_prune_recusa_shard_vazio(engine, tmp_path):
    sync_records([rec("cebraspe-2024-pf-escrivao-001")], engine)
    shard_dir = tmp_path / "shards"
    shard_dir.mkdir()
    vazio = {
        "evento": "PF_24", "banca": "Cebraspe", "orgaos": [], "cargos": [],
        "assuntos": [], "provas": [], "itens": [],
    }
    path = shard_dir / "PF_24.json"
    path.write_text(json.dumps(vazio), encoding="utf-8")
    with pytest.raises(ValueError, match="shard vazio"):
        sync_shard(path, engine, prune=True)
    assert count(engine, QuestaoDB) == 1
    assert count(engine, Prova) == 1


def test_prune_preserva_texto_referenciado_e_remove_somente_orfaos(engine, tmp_path):
    texto = {"ref": "T1", "conteudo": "texto-base", "citacao": "",
             "imagem": False}
    fonte2 = "https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p2.pdf"
    q1 = rec("cebraspe-2024-pf-escrivao-001", texto=texto)
    q2 = rec("cebraspe-2024-pf-escrivao-002", fonte=fonte2)
    sync_records([q1, q2], engine)

    shard_dir = tmp_path / "shards"
    write_shard("PF_24", [q2], shard_dir)
    sync_shard(shard_dir / "PF_24.json", engine)

    with Session(engine) as s:
        antiga = s.scalar(select(Texto))
        qkeep = s.scalar(select(QuestaoDB).where(QuestaoDB.id == q2["id"]))
        qkeep.texto_id = antiga.id
        s.add(Texto(prova_id=antiga.prova_id, ref="ORFAO", conteudo="órfão"))
        s.commit()
        antiga_id = antiga.id

    apagados = prune_event(engine, "PF_24", {q2["id"]})
    assert apagados == 1
    assert count(engine, QuestaoDB) == 1
    assert count(engine, Prova) == 2
    assert count(engine, Texto) == 1
    with Session(engine) as s:
        t = s.scalar(select(Texto))
        qkeep = s.scalar(select(QuestaoDB).where(QuestaoDB.id == q2["id"]))
        assert t.id == antiga_id and qkeep.texto_id == antiga_id


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


def test_cli_prune_exige_evento(tmp_path, capsys):
    code = db.main([
        "sync", "--url", f"sqlite:///{tmp_path / 't.db'}",
        "--shard-dir", str(tmp_path), "--prune",
    ])
    assert code == 2
    assert "--prune exige --evento" in capsys.readouterr().err


def test_cli_evento_inexistente_ou_invalido_falha(tmp_path, capsys):
    url = f"sqlite:///{tmp_path / 't.db'}"
    code = db.main([
        "sync", "--url", url, "--shard-dir", str(tmp_path),
        "--evento", "NAO_EXISTE",
    ])
    assert code == 2
    assert "shard não encontrado" in capsys.readouterr().err
    code = db.main([
        "sync", "--url", url, "--shard-dir", str(tmp_path),
        "--evento", "../ABIN_17",
    ])
    assert code == 2
    assert "nome de evento inválido" in capsys.readouterr().err


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
