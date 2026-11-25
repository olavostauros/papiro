"""api.main — endpoints sobre SQLite (mesma engine que o sync usa)."""

from __future__ import annotations

import importlib.util

import pytest

from crawler import db

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("sqlalchemy") is None
    or importlib.util.find_spec("fastapi") is None,
    reason="sqlalchemy/fastapi não instalados",
)


def rec(qid, **kw):
    base = dict(
        id=qid, banca="Cebraspe", orgao="Polícia Federal",
        cargo="Escrivão de Polícia Federal", ano=2024, assunto="Direito Penal",
        tipo="certo_errado", enunciado=f"enunciado {qid} palavra-chave",
        alternativas=["Certo", "Errado"], gabarito="certo",
        fonte="https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p1.pdf")
    base.update(kw)
    return base


RECS = [
    rec("cebraspe-2024-pf-escrivao-001",
        enunciado="enunciado órgão palavra-chave"),
    rec("cebraspe-2024-pf-escrivao-002", gabarito="errado"),
    rec("cebraspe-2023-pf-escrivao-001", ano=2023, assunto="",
        fonte="https://cdn.cebraspe.org.br/concursos/PF_23/arquivos/p1.pdf"),
    rec("fcc-2024-tj-analista-001", banca="FCC", orgao="TJ", cargo="Analista",
        tipo="multipla_escolha", alternativas=["A", "B", "C", "D", "E"],
        gabarito="b", enunciado="texto sem a marca",
        fonte="https://example.com/prova.pdf"),
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.undo()  # libera httpx p/ TestClient (transport ASGI, sem rede)
    from fastapi.testclient import TestClient

    from api.main import create_app

    url = f"sqlite:///{tmp_path / 't.db'}"
    engine = db.get_engine(url)
    db.create_schema(engine)
    db.sync_records(RECS, engine)
    return TestClient(create_app(url))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_questoes_pagina_e_shape(client):
    r = client.get("/questoes", params={"per_page": 2})
    body = r.json()
    assert body["total"] == 4 and body["pages"] == 2
    assert len(body["items"]) == 2
    q = body["items"][0]
    assert set(q) == {"id", "banca", "orgao", "cargo", "ano", "assunto",
                      "tipo", "enunciado", "alternativas", "gabarito", "fonte",
                      "texto"}
    assert q["ano"] == 2024  # ordenado por ano desc


def test_questoes_filtros(client):
    r = client.get("/questoes", params={"banca": "FCC"})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["alternativas"] == ["A", "B", "C", "D", "E"]
    r = client.get("/questoes", params={"ano": 2023})
    assert r.json()["total"] == 1
    # NULL alternativas → default ["Certo", "Errado"]; NULL assunto → ""
    assert r.json()["items"][0]["alternativas"] == ["Certo", "Errado"]
    assert r.json()["items"][0]["assunto"] == ""
    r = client.get("/questoes", params={"tipo": "multipla_escolha"})
    assert r.json()["total"] == 1
    r = client.get("/questoes", params={"q": "inexistente"})
    assert r.json()["total"] == 0
    r = client.get("/questoes", params={"q": "palavra-chave", "ano": 2024})
    assert r.json()["total"] == 2


def test_questoes_evento_e_tipo_estrito(client):
    r = client.get("/questoes", params={"evento": "PF_24"})
    assert r.json()["total"] == 2
    r = client.get("/questoes", params={"evento": "NAO_EXISTE"})
    assert r.json()["total"] == 0
    assert client.get("/questoes", params={"tipo": "xpto"}).status_code == 422


def test_questoes_q_sem_acento(client):
    # "órgão" no enunciado do rec 001 casa busca sem acento
    r = client.get("/questoes", params={"q": "orgao"})
    assert r.json()["total"] == 1
    r = client.get("/filtros/cargo", params={"q": "escrivao"}).json()
    assert [f["valor"] for f in r] == ["Escrivão de Polícia Federal"]


def test_questao_por_id_e_404(client):
    q = client.get("/questoes/fcc-2024-tj-analista-001").json()
    assert q["gabarito"] == "b"
    assert client.get("/questoes/nao-existe").status_code == 404


def test_filtros_cascata(client):
    r = client.get("/filtros").json()
    assert r["bancas"] == ["Cebraspe", "FCC"]
    assert r["anos"] == [2024, 2023]
    assert "Direito Penal" in r["assuntos"]
    # cascata: filtrar por FCC restringe orgaos/cargos/anos, não a lista de bancas
    r = client.get("/filtros", params={"banca": "FCC"}).json()
    assert r["bancas"] == ["Cebraspe", "FCC"]
    assert r["orgaos"] == ["TJ"]
    assert r["anos"] == [2024]


def test_filtros_dims_e_evento(client):
    r = client.get("/filtros", params={"dims": "banca,ano"}).json()
    assert set(r) == {"bancas", "anos"}
    assert client.get("/filtros", params={"dims": "foo"}).status_code == 422
    r = client.get("/filtros", params={"evento": "PF_24",
                                       "dims": "ano"}).json()
    assert r == {"anos": [2024]}


def test_faceta(client):
    r = client.get("/filtros/cargo").json()
    esc = next(f for f in r if f["valor"].startswith("Escrivão"))
    assert esc["questoes"] == 3
    # busca no valor da faceta (não no enunciado)
    r = client.get("/filtros/cargo", params={"q": "analista"}).json()
    assert [f["valor"] for f in r] == ["Analista"]
    # cascata: outros filtros restringem, o próprio dim não
    r = client.get("/filtros/cargo", params={"banca": "FCC",
                                             "cargo": "Inexistente"}).json()
    assert [f["valor"] for f in r] == ["Analista"]
    r = client.get("/filtros/ano").json()
    assert [f["valor"] for f in r] == ["2024", "2023"]
    assert client.get("/filtros/peso").status_code == 404


def test_eventos_e_provas(client):
    evs = {e["evento"]: e for e in client.get("/eventos").json()}
    ev = evs["PF_24"]
    assert ev["questoes"] == 2 and ev["provas"] == 1
    assert ev["orgaos"] == ["Polícia Federal"]
    assert ev["cargos"] == ["Escrivão de Polícia Federal"]
    assert ev["anos"] == [2024]
    provas = client.get("/provas", params={"evento": "PF_24"}).json()
    assert len(provas) == 1 and provas[0]["questoes"] == 2
    assert provas[0]["fonte"].endswith("p1.pdf")
    assert provas[0]["cargos"] == ["Escrivão de Polícia Federal"]
    assert provas[0]["anos"] == [2024]
    assert provas[0]["tipos"] == ["certo_errado"]


def test_questoes_filtro_fonte(client):
    fonte = "https://cdn.cebraspe.org.br/concursos/PF_23/arquivos/p1.pdf"
    r = client.get("/questoes", params={"fonte": fonte})
    assert r.json()["total"] == 1
    r = client.get("/questoes", params={"evento": "PF_24", "fonte": fonte})
    assert r.json()["total"] == 0
