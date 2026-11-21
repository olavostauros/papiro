import json

from crawler import extract_local as xl
from crawler.tests.conftest import requires_pdftotext


def _cd(fixtures):
    texto = (fixtures / "prova_cd26pl_cg.layout.txt").read_text(encoding="utf-8")
    gab = {int(k): v for k, v in json.loads(
        (fixtures / "gab_cd26pl_cg.json").read_text(encoding="utf-8")).items()}
    return texto, gab


def test_cd26pl_todos_os_itens_na_ordem_certa(fixtures):
    texto, gab = _cd(fixtures)
    itens = xl.itens_do_texto(texto, gab)
    assert sorted(itens) == list(range(1, 91))
    # os itens que o Firecrawl pulou/renumerou estão no lugar certo
    assert itens[84].startswith("Por não possuírem um formato predefinido")
    assert itens[87].startswith("Value, pilar fundamental do Big Data")
    assert itens[90].startswith("Em sistemas de IA generativa")
    assert "predição iterativa" in itens[90]          # o Firecrawl escreveu "literativa"


def test_cd26pl_item_com_lista_e_cabecalho_fora(fixtures):
    texto, gab = _cd(fixtures)
    itens = xl.itens_do_texto(texto, gab)
    # premissas A/B/C na borda da coluna fazem parte do item 41
    assert itens[41].startswith("Considere as seguintes proposições de determinado deputado:")
    assert "B: “Se sou punido pela legenda" in itens[41]
    assert itens[41].endswith("os eleitores não poderão ficar decepcionados.")
    # cabeçalho da página não vaza para o fim do item
    assert "CEBRASPE" not in itens[15]
    # comando "julgue…" e texto-base não entram no item
    assert all("julgue" not in t.lower() for t in itens.values())


@requires_pdftotext
def test_pdf_pf25_cb1(fixtures):
    itens = xl.itens_do_pdf(fixtures / "prova_pf25_cb1.pdf", range(1, 51))
    assert sorted(itens) == list(range(1, 51))
    assert itens[1] == ("Para seu propósito comunicativo, os autores empregam no texto, "
                        "majoritariamente, a tipologia expositiva.")
    # item com linha em branco no meio (sobra da coluna direita no -layout)
    assert itens[14] == ("O MS Excel permite a identificação de células precedentes e dependentes "
                         "a partir de determinada célula, desde que ela possua uma fórmula associada.")


def test_colunas_sinteticas():
    pagina = "\n".join([
        "Julgue os itens a seguir.                       12 Item da direita que",
        "                                                     continua aqui.",
        "10 Primeiro item da esquerda                    ",
        "     com continuação.                           13 Outro item.",
        "11 Segundo item.                                ",
        "                                                ",
        "Texto-base qualquer da próxima questão,         ",
        "com base no qual julgue os itens.               ",
    ])
    itens = xl.itens_do_texto(pagina, range(10, 14))
    assert itens == {10: "Primeiro item da esquerda com continuação.", 11: "Segundo item.",
                     12: "Item da direita que continua aqui.", 13: "Outro item."}


def test_texto_na_borda_apos_frase_completa_e_texto_base():
    # frase completa + linha na borda com maiúscula = começo de texto-base
    assert xl.itens_do_texto("1 Item completo.\nLinha solta.", [1]) == {1: "Item completo."}
    # frase interrompida: a linha desalinhada pelo -layout continua o item
    assert xl.itens_do_texto("1 Se duas placas forem\ndia entre as placas.", [1]) == \
        {1: "Se duas placas forem dia entre as placas."}
    # depois de ":", as linhas na borda são a lista do item
    assert xl.itens_do_texto("1 Considere:\nA: x.\nB: y.\n     Nesse caso, z.", [1]) == \
        {1: "Considere: A: x. B: y. Nesse caso, z."}


def test_capa_com_instrucoes_numeradas_e_ignorada():
    texto = ("7 A desobediência a qualquer das instruções.\n-- PROVA OBJETIVA --\n"
             "Julgue os itens.\n7 Item de verdade.")
    assert xl.itens_do_texto(texto, [7]) == {7: "Item de verdade."}


def test_letras_matematicas():
    assert xl._juntar(["\U0001D44B e \U0001D44C são independentes."]) == \
        "X e Y são independentes."


def test_codigo_de_barras_do_rodape_e_ignorado():
    assert xl.itens_do_texto("1 Item.\n82201201497573", [1]) == {1: "Item."}


def test_numeracao_de_linha_e_instrucoes_nao_viram_item():
    texto = "\n".join([
        "1 Ao receber este caderno, confira…",   # instrução numerada fora do gabarito
        "Julgue os itens.",
        "51 Item de verdade.",
        "4",                                     # número de linha solto do texto-base
        "52 Outro item.",
    ])
    assert xl.itens_do_texto(texto, [51, 52]) == {51: "Item de verdade.", 52: "Outro item."}


def test_juntar_hifen_e_simbolos():
    assert xl._juntar(["impedi-", "los de brincar"]) == "impedi-los de brincar"
    assert xl._juntar(["admin'--", "Nesse caso"]) == "admin'-- Nesse caso"
    assert xl._juntar(["X afirmou:", " Z afirmou"]) == "X afirmou: Z afirmou"


def test_ilegiveis():
    assert xl.ilegiveis({1: "texto normal", 2: "forma geral ‫ ܫ"}) == [2]
