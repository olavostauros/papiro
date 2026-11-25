"""``_anos_do_nome`` + aviso meta.ano×nome do evento (caso HUB_21: a API
reporta o ano do edital, não do programa)."""

from crawler.__main__ import _anos_do_nome


def test_token_de_dois_digitos():
    assert _anos_do_nome("HUB_21_MULTIPROFISSIONAL") == {2021}
    assert _anos_do_nome("PF_24") == {2024}


def test_token_de_quatro_digitos():
    assert _anos_do_nome("IBGE_2024") == {2024}


def test_numero_de_processo_nao_e_ano():
    # o `_2` de APEX_BRASIL_22_2 é o processo, não um ano
    assert _anos_do_nome("APEX_BRASIL_22_2") == {2022}


def test_sem_token_ano():
    assert _anos_do_nome("CD26PL") == set()
    assert _anos_do_nome("FUVEST") == set()
