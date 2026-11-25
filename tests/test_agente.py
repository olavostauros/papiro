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


def _sample_edital_json(qtd_topicos: int = 8) -> dict[str, Any]:
    base = [
        {"disciplina": "Direito Administrativo", "topico": "Atos administrativos", "prioridade": "alta", "termo_busca": "ato administrativo"},
        {"disciplina": "Direito Administrativo", "topico": "Motivação dos atos", "prioridade": "alta", "termo_busca": "motivacao"},
        {"disciplina": "Direito Administrativo", "topico": "Licenças", "prioridade": "media", "termo_busca": "licenca"},
        {"disciplina": "Direito Constitucional", "topico": "Controle de constitucionalidade", "prioridade": "media", "termo_busca": "constitucionalidade"},
        {"disciplina": "Língua Portuguesa", "topico": "Crase", "prioridade": "baixa", "termo_busca": "crase"},
        {"disciplina": "Direito Penal", "topico": "Crimes contra a administração", "prioridade": "media", "termo_busca": "peculato"},
        {"disciplina": "Tópico Extra 7", "topico": "Não deve entrar", "prioridade": "baixa", "termo_busca": "extra7"},
        {"disciplina": "Tópico Extra 8", "topico": "Não deve entrar", "prioridade": "baixa", "termo_busca": "extra8"},
    ]
    return {
        "resumo": "Edital focado em Direito Administrativo e interpretação.",
        "banca_identificada": "Cebraspe",
        "topicos": base[:qtd_topicos],
    }


def test_edital_sucesso_max_6_topicos_e_contagem_real(client, monkeypatch):
    seen_payloads: list[dict[str, Any]] = []

    def fake_post(url, headers, payload, timeout):
        seen_payloads.append(payload)
        return _gemini_ok_response(_sample_edital_json(8))

    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    texto = (
        "Concurso Público Cebraspe. Conhecimentos Específicos: "
        "1. Atos administrativos: conceito, requisitos, vinculação e motivação. "
        "2. Controle de legalidade e licenças administrativas."
    )
    r = client.post(
        "/agente/edital",
        json={"texto_edital": texto, "cargo": "Escrivão"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["modelo"] == "gemini-4-hydrogen"
    assert body["banca_identificada"] == "Cebraspe"
    assert len(body["topicos"]) == 6
    assert "<conteudo_edital>" in seen_payloads[0]["input"]

    por_termo = {t["termo_busca"]: t for t in body["topicos"]}
    assert por_termo["ato administrativo"]["questoes_disponiveis"] == 3
    assert por_termo["motivacao"]["questoes_disponiveis"] == 2
    assert por_termo["licenca"]["questoes_disponiveis"] == 0  # FCC foi filtrada por banca=Cebraspe
    assert por_termo["ato administrativo"]["filtro_sugerido"] == {
        "q": "ato administrativo",
        "banca": "Cebraspe",
    }
    assert all(t["timeout_consulta"] is False for t in body["topicos"])
    assert body["tempo_total_consultas_ms"] >= 0


def test_edital_timeout_consulta_degrada_sem_quebrar(client, monkeypatch):
    monkeypatch.setattr(
        agente,
        "_post_interaction",
        lambda *a, **k: _gemini_ok_response(_sample_edital_json(2)),
    )
    monkeypatch.setattr(
        agente,
        "_contar_questoes_por_termo",
        lambda session, termo, banca, timeout_ms: (None, True, 2501),
    )

    r = client.post(
        "/agente/edital",
        json={"texto_edital": "Conteúdo programático de exemplo suficientemente longo para validação."},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["topicos"]) == 2
    assert all(t["timeout_consulta"] is True and t["questoes_disponiveis"] is None for t in body["topicos"])
    assert body["tempo_total_consultas_ms"] == 5002


def test_edital_curto_422(client):
    r = client.post("/agente/edital", json={"texto_edital": "curto demais"})
    assert r.status_code == 422


def test_edital_sem_api_key_503(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = client.post(
        "/agente/edital",
        json={"texto_edital": "Conteúdo programático de exemplo suficientemente longo para validação."},
    )
    assert r.status_code == 503


def test_edital_fallback_503_para_modelo_secundario(client, monkeypatch):
    calls: list[str] = []

    def fake_post(url, headers, payload, timeout):
        calls.append(payload["model"])
        if payload["model"] == "gemini-4-hydrogen":
            return httpx.Response(503, json={"error": {"message": "high demand"}})
        return _gemini_ok_response(_sample_edital_json(3))

    monkeypatch.setattr(agente.time, "sleep", lambda _: None)
    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    r = client.post(
        "/agente/edital",
        json={"texto_edital": "Conteúdo programático de exemplo suficientemente longo para validação."},
    )
    assert r.status_code == 200
    assert r.json()["modelo"] == "gemini-3.5-flash-lite"
    assert calls == [
        "gemini-4-hydrogen",
        "gemini-4-hydrogen",
        "gemini-3.5-flash-lite",
    ]


def test_explicar_texto_base_ausente_curto_circuito(tmp_path, monkeypatch):
    recs = RECS + [
        _rec(
            "cebraspe-2026-agepar-001",
            tipo="multipla_escolha",
            enunciado="Com base nas ideias expressas no texto CG1A1, é correto afirmar que",
            alternativas=["Opt A", "Opt B", "Opt C", "Opt D correta", "Opt E"],
            gabarito="d",
            fonte="https://cdn.cebraspe.org.br/concursos/AGEPAR_26/prova.pdf",
        ),
        _rec(
            "cebraspe-2025-exemplo-001",
            enunciado="Segundo o texto I, o autor defende a reforma tributária.",
            gabarito="certo",
        ),
        _rec(
            "cebraspe-2025-exemplo-002",
            tipo="multipla_escolha",
            enunciado="De acordo com o texto 1A1, assinale a opção correta.",
            alternativas=["Alt A", "Alt B", "Alt C", "Alt D", "Alt E"],
            gabarito="a",
        ),
        _rec(
            "cebraspe-2025-exemplo-003",
            enunciado="No texto, afirma-se que os recursos hídricos são ilimitados.",
            gabarito="errado",
        ),
        _rec(
            "cebraspe-2025-const-004",
            enunciado="Segundo o texto constitucional, compete privativamente à União legislar sobre direito penal.",
            gabarito="certo",
        ),
    ]
    url = f"sqlite:///{tmp_path / 'texto_base.db'}"
    eng = db.get_engine(url)
    db.create_schema(eng)
    db.sync_records(recs, eng)
    if "api.main" not in sys.modules and "DATABASE_URL" not in os.environ:
        monkeypatch.setenv("DATABASE_URL", url)
    from api.main import create_app

    monkeypatch.setenv("AGENTE_RATE_PER_MIN", "30")
    cli = TestClient(create_app(url))

    llm_calls = 0

    def fake_post(*args, **kwargs):
        nonlocal llm_calls
        llm_calls += 1
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    for qid in [
        "cebraspe-2026-agepar-001",
        "cebraspe-2025-exemplo-001",
        "cebraspe-2025-exemplo-002",
        "cebraspe-2025-exemplo-003",
    ]:
        r = cli.post("/agente/explicar", json={"questao_id": qid})
        assert r.status_code == 200
        body = r.json()
        assert body["texto_base_ausente"] is True
        assert body["modelo"] == "nenhum"
        assert body["armadilha_banca"] == ""
        assert body["fonte"] in body["explicacao"]
        assert "não é possível justificar a resposta com base no texto" in body["explicacao"]

    assert llm_calls == 0

    r_const = cli.post("/agente/explicar", json={"questao_id": "cebraspe-2025-const-004"})
    assert r_const.status_code == 200
    assert r_const.json()["texto_base_ausente"] is False
    assert llm_calls == 1


def test_explicar_texto_com_trecho_citado_nao_dispara_ausente(tmp_path, monkeypatch):
    recs = RECS + [
        _rec(
            "cebraspe-2026-agepar-002",
            tipo="multipla_escolha",
            enunciado=(
                'Dos sentidos do texto CG1A1 conclui-se que, no trecho “No total, 101 mil '
                'pessoas em 15 estados foram impactadas pela extração de minerais da transição, '
                'que desencadeou 380 confrontos”, o vocábulo “que” retoma'
            ),
            alternativas=["A", "B", "C", "extração de minerais da transição", "E"],
            gabarito="d",
        )
    ]
    url = f"sqlite:///{tmp_path / 'trecho.db'}"
    eng = db.get_engine(url)
    db.create_schema(eng)
    db.sync_records(recs, eng)
    from api.main import create_app

    cli = TestClient(create_app(url))
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente, "_post_interaction", fake_post)
    r = cli.post("/agente/explicar", json={"questao_id": "cebraspe-2026-agepar-002"})
    assert r.status_code == 200
    assert r.json()["texto_base_ausente"] is False
    assert called is True


def test_explicar_mc_envia_todas_alternativas_no_prompt(client, monkeypatch):
    seen: list[dict[str, Any]] = []

    def fake_post(url, headers, payload, timeout):
        seen.append(payload)
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    r = client.post("/agente/explicar", json={"questao_id": "fcc-2024-tj-analista-001"})
    assert r.status_code == 200
    prompt_in = seen[0]["input"]
    sys_inst = seen[0]["system_instruction"]
    for alt in ["A) Ato vinculado", "B) Ato precário", "C) Ato revogável", "D) Ato nulo", "E) Ato tácito"]:
        assert alt in prompt_in
    assert "MÚLTIPLA ESCOLHA" in sys_inst
    assert "letra da alternativa correta" in sys_inst
    assert "RIGOR NORMATIVO" in sys_inst
    assert "costumam vedar" in sys_inst


def test_edital_termo_max_2_palavras_e_retry_menor_que_5(tmp_path, monkeypatch):
    extra_recs = RECS + [
        _rec(
            f"cebraspe-2024-pf-escrivao-{100 + i}",
            enunciado=f"Sobre a licitação pública realizada pelo órgão ({i}).",
        )
        for i in range(6)
    ]
    url = f"sqlite:///{tmp_path / 'edital_retry.db'}"
    eng = db.get_engine(url)
    db.create_schema(eng)
    db.sync_records(extra_recs, eng)
    from api.main import create_app

    cli = TestClient(create_app(url))
    monkeypatch.setattr(
        agente,
        "_post_interaction",
        lambda *a, **k: _gemini_ok_response(
            {
                "resumo": "Edital de teste.",
                "banca_identificada": "",
                "topicos": [
                    {
                        "disciplina": "Direito Constitucional",
                        "topico": "Controle de constitucionalidade",
                        "prioridade": "alta",
                        "termo_busca": "controle de constitucionalidade",
                    },
                    {
                        "disciplina": "Língua Portuguesa",
                        "topico": "Interpretação",
                        "prioridade": "media",
                        "termo_busca": "interpretacao de textos",
                    },
                    {
                        "disciplina": "Direito Administrativo",
                        "topico": "Licitações específicas",
                        "prioridade": "alta",
                        "termo_busca": "licitacao obscura",
                    },
                ],
            }
        ),
    )

    r = cli.post(
        "/agente/edital",
        json={"texto_edital": "Conteúdo programático com licitações, controle de constitucionalidade e interpretação."},
    )
    assert r.status_code == 200
    body = r.json()
    topicos = body["topicos"]
    assert all(len(t["termo_busca"].split()) <= 2 for t in topicos)
    assert topicos[0]["termo_busca"] == "constitucionalidade"
    assert topicos[1]["termo_busca"] == "interpretacao"
    # "licitacao obscura" teve 0 (< 5), tentou 1x com "licitacao" e adotou contagem maior
    assert topicos[2]["termo_busca"] == "licitacao"
    assert topicos[2]["questoes_disponiveis"] >= 5


def test_explicar_circuit_breaker_pula_principal_apos_503(client, monkeypatch):
    calls: list[str] = []

    def fake_post(url, headers, payload, timeout):
        model = payload["model"]
        calls.append(model)
        if model == "gemini-4-hydrogen":
            return httpx.Response(503, json={"error": {"message": "high demand"}})
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setenv("AGENTE_PRIMARY_COOLDOWN_S", "300")
    monkeypatch.setattr(agente.time, "sleep", lambda _: None)
    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    r1 = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    assert r1.status_code == 200
    assert r1.json()["modelo"] == "gemini-3.5-flash-lite"

    # Segunda chamada com ID diferente deve pular o principal e ir direto ao fallback
    r2 = client.post("/agente/explicar", json={"questao_id": "fcc-2024-tj-analista-001"})
    assert r2.status_code == 200
    assert r2.json()["modelo"] == "gemini-3.5-flash-lite"

    assert calls == [
        "gemini-4-hydrogen",
        "gemini-4-hydrogen",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash-lite",
    ]


def test_explicar_timeouts_distintos_e_timeout_abre_breaker(client, monkeypatch):
    monkeypatch.delenv("AGENTE_TIMEOUT_S", raising=False)
    monkeypatch.delenv("AGENTE_PRIMARY_TIMEOUT_S", raising=False)
    monkeypatch.delenv("AGENTE_FALLBACK_TIMEOUT_S", raising=False)

    seen: list[tuple[str, float]] = []

    def fake_post(url, headers, payload, timeout):
        model = payload["model"]
        seen.append((model, timeout))
        if model == "gemini-4-hydrogen":
            raise httpx.ReadTimeout("timeout no principal")
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    # ReadTimeout no principal vai direto ao fallback sem gastar outro timeout
    r1 = client.post("/agente/explicar", json={"questao_id": "cebraspe-2024-pf-escrivao-001"})
    assert r1.status_code == 200
    assert r1.json()["modelo"] == "gemini-3.5-flash-lite"

    # Próxima chamada pula direto ao fallback
    r2 = client.post("/agente/explicar", json={"questao_id": "fcc-2024-tj-analista-001"})
    assert r2.status_code == 200
    assert r2.json()["modelo"] == "gemini-3.5-flash-lite"

    assert seen == [
        ("gemini-4-hydrogen", 10.0),
        ("gemini-3.5-flash-lite", 15.0),
        ("gemini-3.5-flash-lite", 15.0),
    ]


def test_explicar_texto_base_ausente_espanhol(tmp_path, monkeypatch):
    recs = RECS + [
        _rec(
            "cebraspe-2022-see-pe-esp-075",
            enunciado="Según el texto, Paola Vicenci dio a luz a tres hijos en un único parto.",
            gabarito="certo",
            fonte="https://cdn.cebraspe.org.br/concursos/SEE_PE_22/arquivos/esp.pdf",
        ),
        _rec(
            "cebraspe-2022-see-pe-esp-076",
            enunciado="De acuerdo con el texto, el autor propone una reforma educativa.",
            gabarito="errado",
            fonte="https://cdn.cebraspe.org.br/concursos/SEE_PE_22/arquivos/esp.pdf",
        ),
    ]
    url = f"sqlite:///{tmp_path / 'espanhol.db'}"
    eng = db.get_engine(url)
    db.create_schema(eng)
    db.sync_records(recs, eng)
    from api.main import create_app

    cli = TestClient(create_app(url))
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        return _gemini_ok_response(_sample_llm_json())

    monkeypatch.setattr(agente, "_post_interaction", fake_post)

    for qid in ("cebraspe-2022-see-pe-esp-075", "cebraspe-2022-see-pe-esp-076"):
        r = cli.post("/agente/explicar", json={"questao_id": qid})
        assert r.status_code == 200
        body = r.json()
        assert body["texto_base_ausente"] is True
        assert body["modelo"] == "nenhum"
        assert body["fonte"] in body["explicacao"]
        assert "não é possível justificar a resposta com base no texto" in body["explicacao"]

    assert called is False
