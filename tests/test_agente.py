"""Testes de Entrega 1 do agente (POST /agente/explicar + script de aquecimento).

Rodam 100% offline sobre SQLite temporário e mocks de ``httpx``/Gemini.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from api import agente, queries
from crawler import db
from scripts.aquecer_cache_agente import aquecer_cache, carregar_ids


def _rec(qid: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": qid,
        "banca": "Cebraspe",
        "orgao": "Polícia Federal",
        "cargo": "Escrivão de Polícia Federal",
        "ano": 2024,
        "assunto": "Conhecimentos Específicos",
        "tipo": "certo_errado",
        "enunciado": (
            f"Ato administrativo vinculado exige motivação expressa ({qid})."
        ),
        "alternativas": ["Certo", "Errado"],
        "gabarito": "certo",
        "fonte": "https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p1.pdf",
    }
    base.update(kw)
    return base


RECS = [
    _rec("cebraspe-2024-pf-escrivao-001"),
    _rec(
        "cebraspe-2023-pf-escrivao-002",
        ano=2023,
        assunto="",
        enunciado="O ato administrativo discricionário também se sujeita ao controle de legalidade.",
        gabarito="certo",
        fonte="https://cdn.cebraspe.org.br/concursos/PF_23/arquivos/p1.pdf",
    ),
    _rec(
        "cebraspe-2022-pf-escrivao-003",
        ano=2022,
        assunto="",
        enunciado="A motivação do ato administrativo deve ser explícita, clara e congruente.",
        gabarito="certo",
        fonte="https://cdn.cebraspe.org.br/concursos/PF_22/arquivos/p1.pdf",
    ),
    _rec(
        "fcc-2024-tj-analista-001",
        banca="FCC",
        orgao="TJ",
        cargo="Analista",
        ano=2024,
        assunto="Direito Administrativo",
        tipo="multipla_escolha",
        enunciado="Sobre a licença no direito administrativo, assinale a correta.",
        alternativas=["Ato vinculado", "Ato precário", "Ato revogável", "Ato nulo", "Ato tácito"],
        gabarito="a",
        fonte="https://example.com/prova.pdf",
    ),
]


def _gemini_ok_response(payload_obj: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "steps": [
                {"type": "thought", "summary": [{"type": "text", "text": "analisando"}]},
                {
                    "type": "model_output",
                    "content": [
                        {"type": "text", "text": json.dumps(payload_obj, ensure_ascii=False)}
                    ],
                },
            ],
        },
    )


def _sample_llm_json(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "disciplina_inferida": "Direito Administrativo",
        "explicacao": "O gabarito oficial é CERTO porque o ato vinculado exige observância estrita da lei e motivação.",
        "armadilha_banca": "A banca costuma trocar ato vinculado por discricionário.",
        "conceito_chave": "Motivação e vinculação dos atos administrativos.",
        "pontos_chave": ["Ato vinculado não admite juízo de conveniência", "Motivação expressa"],
        "termo_busca": "ato administrativo",
    }
    data.update(overrides)
    return data


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key-never-logged")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-4-hydrogen")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("AGENTE_RETRY_DELAY_S", "1.0")

    def blocked_network(*args, **kwargs):
        raise RuntimeError("teste tentou acesso real à rede")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked_network)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", blocked_network
    )
    monkeypatch.setattr(agente, "_post_interaction", blocked_network)


@pytest.fixture
def client(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'agente.db'}"
    if "api.main" not in sys.modules and "DATABASE_URL" not in os.environ:
        monkeypatch.setenv("DATABASE_URL", url)
    from api.main import create_app

    engine = db.get_engine(url)
    db.create_schema(engine)
    db.sync_records(RECS, engine)
    return TestClient(create_app(url))


def test_explicar_sucesso_e_ancoragem_gabarito(client, monkeypatch):
    seen_payloads: list[dict[str, Any]] = []

    def fake_post(url, headers, payload, timeout):
        seen_payloads.append(payload)
        assert headers["Api-Revision"] == "2026-05-20"
        assert payload["store"] is False
        assert payload["generation_config"] == {"thinking_level": "low"}
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    r = client.post(
        "/agente/explicar",
        json={
            "questao_id": "cebraspe-2024-pf-escrivao-001",
            "resposta_usuario": "errado",
            "duvida": "Por que exige motivação?",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["questao_id"] == "cebraspe-2024-pf-escrivao-001"
    assert body["gabarito_oficial"] == "certo"
    assert body["fonte"] == "https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p1.pdf"
    assert body["anulada"] is False
    assert body["acertou"] is False
    assert body["disciplina_inferida"] == "Direito Administrativo"
    assert body["modelo"] == "gemini-4-hydrogen"
    assert body["cached"] is False
    assert len(seen_payloads) == 1
    assert "<duvida_usuario>" in seen_payloads[0]["input"]

    rel_ids = [q["id"] for q in body["questoes_relacionadas"]]
    assert "cebraspe-2024-pf-escrivao-001" not in rel_ids
    assert set(rel_ids) == {
        "cebraspe-2023-pf-escrivao-002",
        "cebraspe-2022-pf-escrivao-003",
    }


def test_explicar_cache_hit(client, monkeypatch):
    calls = 0

    def fake_post(url, headers, payload, timeout):
        nonlocal calls
        calls += 1
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    r1 = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    r2 = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    assert r1.status_code == 200 and r1.json()["cached"] is False
    assert r2.status_code == 200 and r2.json()["cached"] is True
    assert calls == 1


def test_explicar_404_questao_inexistente(client, monkeypatch):
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    r = client.post("/agente/explicar", json={"questao_id": "nao-existe-999"})
    assert r.status_code == 404
    assert called is False


def test_explicar_anulada_curto_circuito(client, monkeypatch):
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    orig_row_to_questao = queries.row_to_questao

    def patched_row_to_questao(row):
        data = orig_row_to_questao(row)
        data["gabarito"] = "x"
        return data

    monkeypatch.setattr(queries, "row_to_questao", patched_row_to_questao)

    r = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    assert r.status_code == 200
    body = r.json()
    assert body["anulada"] is True
    assert body["gabarito_oficial"] == "x"
    assert body["fonte"] == "https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p1.pdf"
    assert body["modelo"] == "nenhum"
    assert called is False


def test_explicar_sem_api_key_retorna_503(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    assert r.status_code == 503
    assert client.get("/health").status_code == 200
    assert client.get("/questoes").status_code == 200


def test_explicar_fallback_principal_503_fallback_200(client, monkeypatch):
    models_called: list[str] = []
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    def fake_post(url, headers, payload, timeout):
        model = payload["model"]
        models_called.append(model)
        if model == "gemini-4-hydrogen":
            return httpx.Response(
                503,
                json={"error": {"code": "service_unavailable", "message": "high demand"}},
            )
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente.time, "sleep", fake_sleep)
    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    r = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    assert r.status_code == 200
    body = r.json()
    assert body["modelo"] == "gemini-3.5-flash-lite"
    assert models_called == [
        "gemini-4-hydrogen",
        "gemini-4-hydrogen",
        "gemini-3.5-flash-lite",
    ]
    assert sleeps == [1.0]


def test_explicar_retry_429_recupera_no_principal(client, monkeypatch):
    models_called: list[str] = []
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    def fake_post(url, headers, payload, timeout):
        models_called.append(payload["model"])
        if len(models_called) == 1:
            return httpx.Response(429, json={"error": {"message": "rate limit"}})
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente.time, "sleep", fake_sleep)
    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    r = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    assert r.status_code == 200
    assert r.json()["modelo"] == "gemini-4-hydrogen"
    assert models_called == ["gemini-4-hydrogen", "gemini-4-hydrogen"]
    assert sleeps == [1.0]


def test_explicar_rate_limit_429(client, monkeypatch):
    monkeypatch.setenv("AGENTE_RATE_PER_MIN", "2")
    monkeypatch.setattr(
        agente,
        "_post_interaction",
        lambda *a, **k: _gemini_ok_response(_sample_llm_json()),
    )

    assert client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"}).status_code == 200
    assert client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"}).status_code == 200
    r3 = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    assert r3.status_code == 429
    assert "retry-after" in {k.lower() for k in r3.headers}


def test_explicar_teto_global_diario_429(client, monkeypatch):
    monkeypatch.setenv("AGENTE_DAILY_GLOBAL_CAP", "1")
    monkeypatch.setattr(
        agente,
        "_post_interaction",
        lambda *a, **k: _gemini_ok_response(_sample_llm_json()),
    )

    r1 = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    r2 = client.post("/agente/explicar", json={"questao_id": "fcc-2024-tj-analista-001"})
    assert r1.status_code == 200
    assert r2.status_code == 429


def test_explicar_guardrail_contradicao(client, monkeypatch):
    monkeypatch.setattr(
        agente,
        "_post_interaction",
        lambda *a, **k: _gemini_ok_response(
            _sample_llm_json(
                explicacao="Na verdade a banca errou e a questão deveria ser anulada.",
                armadilha_banca="Gabarito oficial está errado.",
            )
        ),
    )

    r = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    assert r.status_code == 200
    body = r.json()
    assert "gabarito oficial definitivo" in body["explicacao"].lower()
    assert "CERTO" in body["explicacao"]
    assert body["fonte"] in body["explicacao"]
    assert body["armadilha_banca"] == ""


def test_explicar_resposta_usuario_invalida_422(client):
    r = client.post(
        "/agente/explicar",
        json={"questao_id": "cebraspe-2024-pf-escrivao-001", "resposta_usuario": "a"},
    )
    assert r.status_code == 422


def test_cors_permite_post(client):
    r = client.options(
        "/agente/explicar",
        headers={
            "Origin": "https://olavostauros.github.io",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
    allow_methods = r.headers.get("access-control-allow-methods", "")
    assert "POST" in allow_methods


def test_script_aquecer_cache(client, tmp_path: Path, monkeypatch):
    calls = 0

    def fake_post(url, headers, payload, timeout):
        nonlocal calls
        calls += 1
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    arq = tmp_path / "ids.txt"
    arq.write_text(
        "# comentário\ncebraspe-2024-pf-escrivao-001\n\nfcc-2024-tj-analista-001\ncebraspe-2024-pf-escrivao-001\n",
        encoding="utf-8",
    )
    ids = carregar_ids([], arq)
    assert ids == ["cebraspe-2024-pf-escrivao-001", "fcc-2024-tj-analista-001"]

    res1 = aquecer_cache(ids, base_url="", intervalo=0.0, client=client)
    assert len(res1) == 2
    assert all(item.ok and item.cached is False for item in res1)
    assert calls == 2

    res2 = aquecer_cache(ids, base_url="", intervalo=0.0, client=client)
    assert all(item.ok and item.cached is True for item in res2)
    assert calls == 2
