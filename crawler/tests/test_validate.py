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
