import pytest

from crawler import gabarito as g
from crawler.tests.conftest import requires_pdftotext


@requires_pdftotext
def test_pdf_certo_errado_ibama(fixtures):
    gab = g.parse_pdf(fixtures / "gab_ibama25_cb1.pdf")
    assert gab.itens == list(range(1, 51))
    assert gab.anulados == [15, 49]
    assert gab.tipo == "certo_errado"
    assert gab.codigo == "057_IBAMA_CB1_01"
    assert gab.respostas[1] == "C" and gab.respostas[4] == "E"
    assert gab.para_dataset(1) == "certo" and gab.para_dataset(4) == "errado"
    assert gab.para_dataset(15) is None          # anulado
    assert gab.para_dataset(99) is None          # inexistente


@requires_pdftotext
def test_pdf_multipla_escolha_letras_grudadas(fixtures):
    gab = g.parse_pdf(fixtures / "gab_sebrae24_psi_001_01.pdf")
    assert gab.itens == list(range(1, 51))
    assert gab.tipo == "multipla_escolha"
    assert gab.respostas[1] == "D" and gab.respostas[2] == "C"
    assert gab.para_dataset(1) == "d"


def test_texto_resposta_na_linha_seguinte():
    txt = """
Questão   21 22 23 24
Gabarito
          C   BDA
"""
    gab = g.parse_text(txt)
    assert gab.respostas == {21: "C", 22: "B", 23: "D", 24: "A"}


def test_texto_descarta_celulas_zero():
    txt = """
Item 41 42 43  0  0
Gabarito E  C  X  0  0
"""
    gab = g.parse_text(txt)
    assert gab.itens == [41, 42, 43] and gab.anulados == [43]


def test_texto_sem_respostas_suficientes_falha():
    with pytest.raises(g.GabaritoError):
        g.parse_text("Item 1 2 3 4\nGabarito C E\n")


def test_texto_sem_tabela_falha():
    with pytest.raises(g.GabaritoError):
        g.parse_text("nada aqui")


def test_cache_path():
    p = g.cache_path("https://cdn.cebraspe.org.br/concursos/PF_21/arquivos/GAB.PDF")
    assert p.parts[-2:] == ("PF_21", "GAB.PDF")
