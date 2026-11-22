import json

import pytest

from crawler import ingest as run
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


def _rodar(ambiente, *, extrator, pdf_itens, coord_itens=None, gab_loader=None,
           extractor=None, chamadas=None, teto=30):
    _, ledger, ds_path = ambiente
    return run.executar({"provas": [entrada()]}, run.Dataset.carregar(ds_path), limite=1,
                        teto=teto, extractor=extractor or fake_extractor(
                            range(1, 11), ledger, chamadas=chamadas),
                        gab_loader=gab_loader or fake_gab(), page_counter=lambda u: 2,
                        ledger=ledger, pdf_itens=pdf_itens, coord_itens=coord_itens,
                        extrator=extrator, log=lambda *_: None)


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


# --- parser de coordenadas (motor local primário) ----------------------------

def test_coord_cobre_lacuna_do_texto_sem_credito(ambiente):
    chamadas = []
    rep = _rodar(ambiente, extrator="local",
                 pdf_itens=_locais(range(1, 9)),        # texto perde 9 e 10
                 coord_itens=_locais(range(1, 11)),     # coordenadas cobrem tudo
                 chamadas=chamadas, teto=0)
    p = rep["provas"][0]
    assert chamadas == [] and p["status"] == "aprovada"
    assert p["extrator_por_item"]["9"] == "local(coord)"
    assert p["adicionadas"] == 18


def test_coord_tem_precedencia_na_uniao(ambiente):
    tmp_path, _, ds_path = ambiente
    def coord(url, esperados):
        return {n: f"Item {n} via coordenadas." for n in range(1, 11)}
    rep = _rodar(ambiente, extrator="local", pdf_itens=_locais(range(1, 11)),
                 coord_itens=coord, teto=0)
    p = rep["provas"][0]
    assert p["status"] == "aprovada"
    salvo = json.loads(ds_path.read_text(encoding="utf-8"))
    enun = next(q["enunciado"] for q in salvo
                if q["id"] == "cebraspe-2026-teste-analista-001")
    assert "via coordenadas" in enun


def test_coord_falha_cai_no_motor_de_texto(ambiente):
    def coord_ruim(url, esperados):
        raise RuntimeError("pdftohtml indisponível")
    rep = _rodar(ambiente, extrator="local", pdf_itens=_locais(range(1, 11)),
                 coord_itens=coord_ruim, teto=0)
    assert rep["provas"][0]["status"] == "aprovada"


def test_coord_lacuna_pequena_vai_por_item(ambiente):
    chamadas = []      # 2 itens sem leitura local (39, 40 de 40) → Firecrawl só neles
    parcial = _locais(range(1, 39))
    ext = fake_extractor(range(1, 41), chamadas=chamadas)
    rep = _rodar(ambiente, extrator="hibrido", pdf_itens=parcial,
                 coord_itens=parcial, gab_loader=fake_gab(1, 40),
                 extractor=ext, chamadas=chamadas)
    p = rep["provas"][0]
    assert len(chamadas) == 1 and p["status"] == "aprovada"
    assert p["itens_por_extrator"] == {"local(coord)": 38, "firecrawl": 2}
    assert p["extrator_por_item"]["39"] == "firecrawl"


def test_coord_lacuna_grande_vai_na_prova_inteira(ambiente):
    chamadas = []      # 20 itens sem leitura local → prova inteira no Firecrawl
    parcial = _locais(range(1, 21))
    ext = fake_extractor(range(1, 41), chamadas=chamadas)
    rep = _rodar(ambiente, extrator="hibrido", pdf_itens=parcial,
                 coord_itens=parcial, gab_loader=fake_gab(1, 40),
                 extractor=ext, chamadas=chamadas)
    p = rep["provas"][0]
    assert len(chamadas) == 1 and p["itens_por_extrator"] == {"firecrawl": 40}
    assert "cobertura local" in p["fallback"]


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


# --- priorização ---------------------------------------------------------------

def test_parse_anos():
    from crawler.bancas.cebraspe import selecao
    assert selecao.parse_anos("2022-2024") == {2022, 2023, 2024}
    assert selecao.parse_anos("2021, 2023") == {2021, 2023}
    assert selecao.parse_anos(None) is None


def test_filtros_anos_orgao_prioridade(ambiente):
    _, _, ds_path = ambiente
    ds = run.Dataset.carregar(ds_path)
    man = {"provas": [
        entrada(caderno="tj", evento="TJ_CE_25", orgao="Tribunal de Justiça do Ceará", ano=2025),
        entrada(caderno="pc", evento="PC_PE_26", orgao="Polícia Civil de Pernambuco", ano=2026),
        entrada(caderno="see", evento="SEE_PE_22", evento_nome="SEE PE 22 ANA ASS",
                orgao="Secretaria de Educação de Pernambuco", ano=2022),
        entrada(caderno="anm", evento="ANM_24", orgao="Agência Nacional de Mineração", ano=2024),
        entrada(caderno="mjsp", evento="MJSP_21_PSS", orgao="Ministério da Justiça", ano=2021),
    ]}
    cads = lambda **kw: [e["caderno"] for e in run.selecionar(man, ds, **kw)[0]]
    assert cads(anos={2024, 2025, 2026}) == ["pc", "tj", "anm"]
    assert cads(orgaos=["pernambuco"]) == ["pc", "see"]
    # prioridade define a ordem; "ANA" de Analista e "Justiça" de ministério não casam
    assert cads(prioridade=["policias", "tribunais", "agencias"]) == ["pc", "tj", "anm"]
    with pytest.raises(ValueError):
        run.selecionar(man, ds, prioridade=["inexistente"])


# --- múltipla escolha local e descarte por questão ------------------------------

def _mc_local(nums):
    return lambda url, esperados: {n: (f"Enunciado da questão {n} fim.",
                                       [f"opção {l} da questão {n} fim" for l in "abcde"])
                                   for n in nums}


def _texto_pdf(nums, sem_alternativa=()):
    linhas = []
    for n in nums:
        linhas.append(f"Questão {n}\nEnunciado da questão {n} fim.")
        for l in "abcde":
            if n in sem_alternativa and l == "c":
                linhas.append("C texto diferente no PDF")
            else:
                linhas.append(f"{l.upper()} opção {l} da questão {n} fim")
    return lambda url: "\n".join(linhas)


def _rodar_mc(ambiente, *, nums=range(1, 21), sem_alternativa=(), chamadas=None, teto=0):
    _, ledger, ds_path = ambiente
    mc_gab = lambda url: Gabarito(respostas={n: "B" for n in range(1, 21)}, url=url)
    return run.executar({"provas": [entrada()]}, run.Dataset.carregar(ds_path), limite=1,
                        teto=teto, extractor=fake_extractor(range(1, 21), ledger, chamadas=chamadas),
                        gab_loader=mc_gab, page_counter=lambda u: 2, ledger=ledger,
                        pdf_itens=_locais(range(1, 21)), pdf_mc=_mc_local(nums),
                        pdf_texto=_texto_pdf(range(1, 21), sem_alternativa),
                        extrator="hibrido", log=lambda *_: None)


def test_mc_local_sem_credito(ambiente):
    chamadas = []
    rep = _rodar_mc(ambiente, chamadas=chamadas)
    p = rep["provas"][0]
    assert chamadas == [] and p["status"] == "aprovada", p["validacao"]["erros"]
    assert p["itens_por_extrator"] == {"local": 20} and p["adicionadas"] == 40
    assert p["questoes_descartadas"] == {}


def test_descarte_por_questao_com_90_por_cento(ambiente):
    rep = _rodar_mc(ambiente, sem_alternativa={7, 12})      # 18/20 = 90% passam
    p = rep["provas"][0]
    assert p["status"] == "aprovada"
    assert set(p["questoes_descartadas"]) == {"7", "12"}
    assert "alternativa C não encontrada no PDF" in p["questoes_descartadas"]["7"]
    assert p["extrator_por_item"]["7"].startswith("descartada")
    assert p["adicionadas"] == 36                              # 18 questões × 2 cargos


def test_abaixo_de_90_por_cento_reprova_a_prova(ambiente):
    rep = _rodar_mc(ambiente, sem_alternativa={1, 2, 3})     # 17/20 = 85%
    p = rep["provas"][0]
    assert p["status"] == "reprovada" and p["adicionadas"] == 0
    assert any("85%" in e and "reprovada inteira" in e for e in p["validacao"]["erros"])


def test_mc_cobertura_local_incompleta_vai_para_firecrawl(ambiente):
    rep = _rodar_mc(ambiente, nums=range(1, 15), teto=30)
    assert "cobertura local 70%" in rep["provas"][0]["fallback"]


def test_mc_anulada_com_falha_no_pdf_nao_reprova(ambiente):
    _, ledger, ds_path = ambiente
    mc_gab = lambda url: Gabarito(respostas={n: ("X" if n == 7 else "B") for n in range(1, 21)},
                                  url=url)
    rep = run.executar({"provas": [entrada()]}, run.Dataset.carregar(ds_path), limite=1, teto=0,
                       extractor=fake_extractor(range(1, 21), ledger), gab_loader=mc_gab,
                       page_counter=lambda u: 2, ledger=ledger, pdf_itens=_locais(range(1, 21)),
                       pdf_mc=_mc_local(range(1, 21)),
                       pdf_texto=_texto_pdf(range(1, 21), sem_alternativa={7}),
                       extrator="local", log=lambda *_: None)
    p = rep["provas"][0]
    assert p["status"] == "aprovada", p["validacao"]["erros"]
    assert p["questoes_descartadas"] == {} and p["adicionadas"] == 38   # 19 × 2 cargos
