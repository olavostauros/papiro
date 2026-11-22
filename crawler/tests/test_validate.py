from crawler.gabarito import Gabarito
from crawler.models import ProvaExtraida, QuestaoExtraida
from crawler.validate import formatar, validar

CE = ["Certo", "Errado"]


def prova(nums, enunciado="Item.", alts=CE):
    return ProvaExtraida(questoes=[QuestaoExtraida(numero=n, enunciado=enunciado,
                                                   alternativas=alts) for n in nums])


def gab(n0, n1, anulados=(), resp="C"):
    return Gabarito(respostas={n: ("X" if n in anulados else resp) for n in range(n0, n1 + 1)})


def test_aprovada_desconta_anulados():
    r = validar(prova(range(1, 11)), gab(1, 10, anulados={3}))
    assert r.aprovada, r.erros
    assert r.registros_validos == 9 and r.anulados == [3]
    assert "APROVADA" in formatar(r)


def test_duplicada_e_buraco():
    r = validar(prova([1, 2, 2, 4, 5]), gab(1, 5))
    assert not r.aprovada
    assert any("duplicada: 2" in e for e in r.erros)
    assert any("buracos" in e and "3" in e for e in r.erros)
    assert any("ausentes na extração: 3" in e for e in r.erros)


def test_total_diferente_do_gabarito():
    r = validar(prova(range(51, 100)), gab(51, 120))
    assert not r.aprovada
    assert any("100–120" in e for e in r.erros)


def test_itens_fora_do_gabarito():
    r = validar(prova(range(1, 12)), gab(1, 10))
    assert any("fora do gabarito: 11" in e for e in r.erros)


def test_enunciado_vazio():
    r = validar(prova([1, 2], enunciado="  "), gab(1, 2))
    assert any("enunciado vazio" in e for e in r.erros)


def test_tipo_incompativel():
    r = validar(prova([1, 2], alts=["a", "b", "c", "d", "e"]), gab(1, 2))
    assert any("tipo incompatível" in e for e in r.erros)


def test_enunciado_longo_e_aviso_nao_erro():
    r = validar(prova([1], enunciado="x" * 5000), gab(1, 1))
    assert r.aprovada and any("texto-base" in a for a in r.avisos)


def test_multipla_escolha():
    g = Gabarito(respostas={1: "A", 2: "E", 3: "X"})
    r = validar(prova([1, 2, 3], alts=list("abcde")), g)
    assert r.aprovada and r.registros_validos == 2


# --- cruzamento com o PDF ----------------------------------------------------

def _cd(fixtures):
    import json
    from crawler import extract_local as xl
    texto = (fixtures / "prova_cd26pl_cg.layout.txt").read_text(encoding="utf-8")
    resp = {int(k): v for k, v in json.loads(
        (fixtures / "gab_cd26pl_cg.json").read_text(encoding="utf-8")).items()}
    prova = ProvaExtraida.model_validate_json(
        (fixtures / "firecrawl_cd26pl_cg.json").read_text(encoding="utf-8"))
    return prova, Gabarito(respostas=resp), xl.itens_do_texto(texto, resp)


def test_cd26pl_firecrawl_renumerado_reprova(fixtures):
    prova, gab, itens_pdf = _cd(fixtures)
    r = validar(prova, gab, itens_pdf=itens_pdf)
    assert not r.aprovada
    assert any("renumeração" in e and "84→88, 85→89, 86→90" in e for e in r.erros)
    assert any("pulados pela extração: 84–87" in e for e in r.erros)


def test_cd26pl_reprova_mesmo_com_contagem_fechando(fixtures):
    prova, gab, itens_pdf = _cd(fixtures)
    gab86 = Gabarito(respostas={n: x for n, x in gab.respostas.items() if n <= 86})
    sem_cruzar = validar(prova, gab86)
    assert sem_cruzar.aprovada                          # a contagem sozinha não pega
    r = validar(prova, gab86, itens_pdf=itens_pdf)
    assert not r.aprovada and any("renumeração" in e for e in r.erros)


def test_cruzamento_aceita_texto_base_antes_e_trecho_final():
    from crawler.validate import confere
    item = "A autoridade policial está vinculada ao requerimento do advogado da vítima."
    assert confere("Considerando a situação hipotética, julgue o item. " + item, item)
    assert confere("Com base no argumento cujas premissas sejam A, B e C, é correto concluir",
                   "Considere as seguintes proposições: A: x. Com base no argumento cujas "
                   "premissas sejam A, B e C, é correto concluir")
    assert not confere("Um dos princípios de uma VPN é garantir a privacidade",
                       "O relacionamento N:N entre duas tabelas no modelo lógico")


def test_cruzamento_com_parser_local_falho_so_avisa():
    from crawler.validate import validar as v
    r = v(prova(range(1, 11)), gab(1, 10), itens_pdf={1: "Item."})
    assert r.aprovada and any("não aplicado" in a for a in r.avisos)


# --- múltipla escolha ----------------------------------------------------------

def test_mc_alternativas_fora_de_4_5_reprova():
    g = Gabarito(respostas={1: "A", 2: "B"})
    r = validar(prova([1, 2], alts=["a", "b", "c"]), g)
    assert not r.aprovada and any("fora de 4–5" in e for e in r.erros)


def test_mc_letra_alem_das_alternativas_reprova():
    g = Gabarito(respostas={1: "E", 2: "A"})
    r = validar(prova([1, 2], alts=["a", "b", "c", "d"]), g)
    assert any("letra do gabarito além" in e and "1" in e for e in r.erros)


def test_mc_texto_conferido_no_pdf():
    pdf = ("1 Assinale a opção correta sobre o tema.\nA) primeira opção certa\n"
           "B) segunda\nC) terceira\nD) quarta\n")
    ok = ProvaExtraida(questoes=[QuestaoExtraida(
        numero=1, enunciado="Assinale a opção correta sobre o tema.",
        alternativas=["A) primeira opção certa", "B) segunda", "C) terceira", "D) quarta"])])
    g = Gabarito(respostas={1: "A"})
    assert validar(ok, g, texto_pdf=pdf).aprovada
    inventada = ProvaExtraida(questoes=[QuestaoExtraida(
        numero=1, enunciado="Texto que o modelo inventou e não está na prova.",
        alternativas=["(A) primeira opção certa", "B) alternativa inventada", "C) terceira",
                      "D) quarta"])])
    r = validar(inventada, g, texto_pdf=pdf)
    assert any("enunciado não encontrado" in e for e in r.erros)
    assert any("alternativa não encontrada" in e for e in r.erros)


def test_mc_afirmativas_tomadas_por_alternativas_reprova():
    pdf = ("14 São exemplos de navegadores que permitem ao usuário\nI escrever e-mails.\n"
           "II fazer compras.\nIII ver vídeos.\nIV proteger o computador.\n"
           "Estão certos apenas os itens\nA I e II.\nB I e III.\nC II e IV.\nD I, II e III.\n"
           "E II, III e IV.\n")
    errada = ProvaExtraida(questoes=[QuestaoExtraida(
        numero=14, enunciado="São exemplos de navegadores que permitem ao usuário",
        alternativas=["I escrever e-mails.", "II fazer compras.", "III ver vídeos.",
                      "IV proteger o computador.", "Estão certos apenas os itens"])])
    certa = ProvaExtraida(questoes=[QuestaoExtraida(
        numero=14, enunciado="São exemplos de navegadores que permitem ao usuário I escrever "
                             "e-mails. II fazer compras. III ver vídeos. IV proteger o "
                             "computador. Estão certos apenas os itens",
        alternativas=["A I e II.", "B I e III.", "C II e IV.", "D I, II e III.", "E II, III e IV."])])
    g = Gabarito(respostas={14: "D"})
    assert any("alternativa não encontrada" in e for e in validar(errada, g, texto_pdf=pdf).erros)
    assert validar(certa, g, texto_pdf=pdf).aprovada
