import json

import pytest

from crawler import run
from crawler.gabarito import Gabarito
from crawler.models import ProvaExtraida, QuestaoExtraida

LEDGER = """# ledger

## Totals

| Period       | Credits used |
| ------------ | ------------ |
| All time     | 10 |
| Current week | 10 |

## Log

| Date | Task | Tool | Items | Credits | Notes |
| ---- | ---- | ---- | ----- | ------- | ----- |
| 2026-11-20 | x | y | 1 | 10 | z |
"""


def entrada(caderno="001_TESTE_CB1_01", evento="TESTE_26", **kw):
    e = {
        "evento": evento, "id_evento": 1, "evento_nome": "TESTE 26", "orgao": "Órgão Teste",
        "id_orgao": "teste", "orgao_origem": "eventoNomeCompleto", "ano": 2026,
        "caderno": caderno, "descricao": "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS",
        "fase": "objetiva", "assunto": "Conhecimentos Básicos",
        "cargos": [{"numero": 1, "nome": "Analista", "id_cargo": "analista"},
                   {"numero": 2, "nome": "Técnico", "id_cargo": "tecnico"}],
        "cargo_como": "x",
        "url_prova": f"https://cdn.cebraspe.org.br/concursos/{evento}/arquivos/{caderno}.pdf",
        "url_gabarito": f"https://cdn.cebraspe.org.br/concursos/{evento}/arquivos/GAB_{caderno}.pdf",
        "pareamento": "nome do arquivo",
    }
    e.update(kw)
    return e


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "EXTRACOES", tmp_path / "extracoes")
    ledger = tmp_path / "ledger.md"
    ledger.write_text(LEDGER, encoding="utf-8")
    ds_path = tmp_path / "questions.json"
    ds_path.write_text(json.dumps([{
        "id": "cebraspe-2025-x-y-001", "banca": "Cebraspe", "orgao": "X", "cargo": "Y",
        "ano": 2025, "assunto": "", "tipo": "certo_errado", "enunciado": "e",
        "alternativas": ["Certo", "Errado"], "gabarito": "certo",
        "fonte": "https://cdn.cebraspe.org.br/concursos/JA_25/arquivos/001_JA_CB1_01.pdf"},
        {"id": "cebraspe-2024-z-w-001", "banca": "Cebraspe", "orgao": "Z", "cargo": "W",
         "ano": 2024, "assunto": "", "tipo": "certo_errado", "enunciado": "e",
         "alternativas": ["Certo", "Errado"], "gabarito": "certo",
         "fonte": "https://cdn.cebraspe.org.br/concursos/PASTA_24/arquivos/"}],
        ensure_ascii=False), encoding="utf-8")
    return tmp_path, ledger, ds_path


def fake_extractor(nums, ledger=None, credits=7, chamadas=None):
    from crawler import usage

    def ext(url, task):
        if chamadas is not None:
            chamadas.append(url)
        if ledger is not None and credits:
            usage.log_call(task=task, tool="sdk:scrape[json]", items=1, credits=credits,
                           notes=url, path=ledger)
        return ProvaExtraida(questoes=[QuestaoExtraida(numero=n, enunciado=f"Item {n}.",
                                                       alternativas=["Certo", "Errado"])
                                       for n in nums])
    return ext


def fake_gab(n0=1, n1=10, anulados=(3,)):
    return lambda url: Gabarito(respostas={n: ("X" if n in anulados else "E")
                                           for n in range(n0, n1 + 1)}, url=url)


def test_selecionar_pula_ja_ingeridas(ambiente):
    _, _, ds_path = ambiente
    ds = run.Dataset.carregar(ds_path)
    man = {"provas": [
        entrada(),
        entrada(caderno="001_JA_CB1_01", evento="JA_25"),
        entrada(caderno="002_PASTA_CB1_01", evento="PASTA_24"),
        entrada(caderno="sem_gab", url_gabarito=None),
        entrada(caderno="sem_cargo", cargos=[], cargo_como="cargo não identificado"),
        entrada(caderno="cf", fase="curso_formacao"),
        entrada(caderno="tipo2", descricao="PROVA OBJETIVA – PERFIL 1 – TIPO 2"),
    ]}
    cand, pul = run.selecionar(man, ds)
    assert [e["caderno"] for e in cand] == ["001_TESTE_CB1_01"]
    motivos = {p["caderno"]: p["motivo"] for p in pul}
    assert "já é fonte" in motivos["001_JA_CB1_01"]
    assert "pasta do evento" in motivos["002_PASTA_CB1_01"]
    assert motivos["sem_gab"] == "sem gabarito definitivo"
    assert "TIPO 2" in motivos["tipo2"]


def test_executar_aprova_e_faz_append(ambiente):
    _, ledger, ds_path = ambiente
    ds = run.Dataset.carregar(ds_path)
    rep = run.executar({"provas": [entrada()]}, ds, limite=1, teto=30,
                       extractor=fake_extractor(range(1, 11), ledger, credits=7),
                       gab_loader=fake_gab(), page_counter=lambda u: 3,
                       ledger=ledger, log=lambda *_: None)
    p = rep["provas"][0]
    assert p["status"] == "aprovada" and rep["creditos_gastos"] == 7
    assert p["adicionadas"] == 18            # 9 itens válidos × 2 cargos (anulado 3 fora)
    salvo = json.loads(ds_path.read_text(encoding="utf-8"))
    ids = {q["id"] for q in salvo}
    assert "cebraspe-2026-teste-analista-001" in ids
    assert "cebraspe-2026-teste-tecnico-010" in ids
    assert "cebraspe-2026-teste-analista-003" not in ids   # anulado
    assert all(q["gabarito"] == "errado" for q in salvo if q["id"].startswith("cebraspe-2026"))
    assert run.total_ledger(ledger) == 17


def test_teto_para_antes_de_gastar(ambiente):
    _, ledger, ds_path = ambiente
    chamadas = []
    rep = run.executar({"provas": [entrada()]}, run.Dataset.carregar(ds_path), limite=5,
                       teto=10, extractor=fake_extractor(range(1, 11), ledger, chamadas=chamadas),
                       gab_loader=fake_gab(), page_counter=lambda u: 8,   # 8+4 > 10
                       ledger=ledger, log=lambda *_: None)
    assert chamadas == [] and rep["parado"] and rep["creditos_gastos"] == 0


def test_limite_de_provas(ambiente):
    _, ledger, ds_path = ambiente
    chamadas = []
    man = {"provas": [entrada(caderno=f"00{i}_TESTE_CB1_01") for i in range(3)]}
    rep = run.executar(man, run.Dataset.carregar(ds_path), limite=2, teto=100,
                       extractor=fake_extractor(range(1, 11), ledger, chamadas=chamadas),
                       gab_loader=fake_gab(), page_counter=lambda u: 1,
                       ledger=ledger, log=lambda *_: None)
    assert len(chamadas) == 2 and len(rep["provas"]) == 2


def test_reprovada_nao_entra_no_dataset(ambiente):
    _, ledger, ds_path = ambiente
    antes = ds_path.read_text(encoding="utf-8")
    rep = run.executar({"provas": [entrada()]}, run.Dataset.carregar(ds_path), limite=1,
                       teto=30, extractor=fake_extractor([1, 2, 2, 5], ledger),
                       gab_loader=fake_gab(), page_counter=lambda u: 1,
                       ledger=ledger, log=lambda *_: None)
    assert rep["provas"][0]["status"] == "reprovada"
    assert ds_path.read_text(encoding="utf-8") == antes


def test_gabarito_falha_antes_de_gastar(ambiente):
    _, ledger, ds_path = ambiente
    chamadas = []

    def gab_quebrado(url):
        raise ValueError("pdf estranho")
    rep = run.executar({"provas": [entrada()]}, run.Dataset.carregar(ds_path), limite=1,
                       teto=30, extractor=fake_extractor(range(1, 11), ledger, chamadas=chamadas),
                       gab_loader=gab_quebrado, page_counter=lambda u: 1,
                       ledger=ledger, log=lambda *_: None)
    assert rep["provas"][0]["status"] == "erro" and chamadas == []


def test_cache_de_extracao_nao_gasta_de_novo(ambiente):
    _, ledger, ds_path = ambiente
    chamadas = []
    kw = dict(limite=1, teto=30, gab_loader=fake_gab(), page_counter=lambda u: 1,
              ledger=ledger, log=lambda *_: None)
    run.executar({"provas": [entrada()]}, run.Dataset.carregar(ds_path),
                 extractor=fake_extractor([1, 2], ledger, chamadas=chamadas), **kw)  # reprovada
    rep = run.executar({"provas": [entrada()]}, run.Dataset.carregar(ds_path),
                       extractor=fake_extractor([1, 2], ledger, chamadas=chamadas), **kw)
    assert len(chamadas) == 1
    assert rep["provas"][0]["cache"] and rep["creditos_gastos"] == 0


def test_sem_credits_used_registra_estimativa(ambiente):
    _, ledger, ds_path = ambiente
    rep = run.executar({"provas": [entrada()]}, run.Dataset.carregar(ds_path), limite=1,
                       teto=30, extractor=fake_extractor(range(1, 11), ledger=None),
                       gab_loader=fake_gab(), page_counter=lambda u: 2,
                       ledger=ledger, log=lambda *_: None)
    assert rep["creditos_gastos"] == 6                     # 2 páginas + 4
    assert run.total_ledger(ledger) == 16
    assert "estimativa" in ledger.read_text(encoding="utf-8")


def test_cli_exige_teto_fora_do_dry_run(tmp_path):
    man = tmp_path / "m.json"
    man.write_text(json.dumps({"resumo": {}, "provas": []}), encoding="utf-8")
    with pytest.raises(SystemExit):
        run.main(["--manifesto", str(man), "--dataset", str(tmp_path / "q.json")])


def test_cli_dry_run_zero_credito(tmp_path, capsys):
    man = tmp_path / "m.json"
    man.write_text(json.dumps({"resumo": {"provas": 1}, "provas": [entrada()]}), encoding="utf-8")
    assert run.main(["--dry-run", "--manifesto", str(man),
                     "--dataset", str(tmp_path / "q.json")]) == 0
    assert "candidatas: 1" in capsys.readouterr().out


# --- modo híbrido ------------------------------------------------------------

def _locais(nums, ilegiveis=()):
    def pdf_itens(url, esperados):
        return {n: (f"Item {n} com ‫ fórmula." if n in ilegiveis else f"Item {n}.")
                for n in nums}
    return pdf_itens


def _rodar(ambiente, *, extrator, pdf_itens, gab_loader=None, chamadas=None, teto=30):
    _, ledger, ds_path = ambiente
    return run.executar({"provas": [entrada()]}, run.Dataset.carregar(ds_path), limite=1,
                        teto=teto, extractor=fake_extractor(range(1, 11), ledger,
                                                            chamadas=chamadas),
                        gab_loader=gab_loader or fake_gab(), page_counter=lambda u: 2,
                        ledger=ledger, pdf_itens=pdf_itens, extrator=extrator,
                        log=lambda *_: None)


def test_hibrido_100_local_nao_gasta(ambiente):
    chamadas = []
    rep = _rodar(ambiente, extrator="hibrido", pdf_itens=_locais(range(1, 11)), chamadas=chamadas)
    p = rep["provas"][0]
    assert chamadas == [] and rep["creditos_gastos"] == 0
    assert p["status"] == "aprovada" and p["itens_por_extrator"] == {"local": 10}
    assert p["adicionadas"] == 18


def test_hibrido_formula_usa_firecrawl_so_no_item(ambiente):
    chamadas = []
    rep = _rodar(ambiente, extrator="hibrido", pdf_itens=_locais(range(1, 11), ilegiveis={5}),
                 chamadas=chamadas)
    p = rep["provas"][0]
    assert len(chamadas) == 1 and rep["creditos_gastos"] == 7
    assert p["status"] == "aprovada", p["validacao"]["erros"]
    assert p["extrator_por_item"]["5"] == "firecrawl"
    assert p["itens_por_extrator"] == {"local": 9, "firecrawl": 1}
    assert "fórmula ilegível" in p["fallback"]


def test_hibrido_formula_em_anulado_nao_gasta(ambiente):
    chamadas = []      # item 3 é anulado no fake_gab: fórmula nele não importa
    rep = _rodar(ambiente, extrator="hibrido", pdf_itens=_locais(range(1, 11), ilegiveis={3}),
                 chamadas=chamadas)
    assert chamadas == [] and rep["provas"][0]["status"] == "aprovada"


def test_hibrido_cobertura_incompleta_vai_para_firecrawl_na_prova(ambiente):
    chamadas = []
    rep = _rodar(ambiente, extrator="hibrido", pdf_itens=_locais(range(1, 9)), chamadas=chamadas)
    p = rep["provas"][0]
    assert len(chamadas) == 1 and p["itens_por_extrator"] == {"firecrawl": 10}
    assert "cobertura local 80%" in p["fallback"]


def test_hibrido_multipla_escolha_vai_para_firecrawl(ambiente):
    chamadas = []
    mc = lambda url: Gabarito(respostas={n: "A" for n in range(1, 11)}, url=url)
    rep = _rodar(ambiente, extrator="hibrido", pdf_itens=_locais(range(1, 11)),
                 gab_loader=mc, chamadas=chamadas)
    assert len(chamadas) == 1 and "múltipla escolha" in rep["provas"][0]["fallback"]


def test_local_omite_formula_e_nunca_gasta(ambiente):
    chamadas = []
    rep = _rodar(ambiente, extrator="local", pdf_itens=_locais(range(1, 11), ilegiveis={5}),
                 chamadas=chamadas, teto=0)
    p = rep["provas"][0]
    assert chamadas == [] and p["status"] == "aprovada"
    assert p["extrator_por_item"]["5"].startswith("omitido")
    assert p["adicionadas"] == 16          # 8 itens (sem o anulado 3 e o 5) × 2 cargos


def test_local_cobertura_incompleta_erro_sem_gastar(ambiente):
    chamadas = []
    rep = _rodar(ambiente, extrator="local", pdf_itens=_locais(range(1, 9)), chamadas=chamadas,
                 teto=0)
    assert chamadas == [] and rep["provas"][0]["status"] == "erro"


def test_firecrawl_forcado(ambiente):
    chamadas = []
    rep = _rodar(ambiente, extrator="firecrawl", pdf_itens=_locais(range(1, 11)),
                 chamadas=chamadas)
    assert len(chamadas) == 1 and rep["provas"][0]["itens_por_extrator"] == {"firecrawl": 10}


def test_teto_zero_prova_local_passa(ambiente):
    chamadas = []      # teto 0: prova 100% local não gasta, então passa
    rep = _rodar(ambiente, extrator="hibrido", pdf_itens=_locais(range(1, 11)), teto=0,
                 chamadas=chamadas)
    assert rep["provas"][0]["status"] == "aprovada" and chamadas == []


def test_teto_zero_fallback_para_antes_de_gastar(ambiente):
    chamadas = []
    rep = _rodar(ambiente, extrator="hibrido", pdf_itens=_locais(range(1, 11), ilegiveis={5}),
                 teto=0, chamadas=chamadas)
    assert rep["parado"] and chamadas == []
