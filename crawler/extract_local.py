"""Extrator LOCAL (zero crédito) para provas certo/errado da Cebraspe.

Protótipo: usa só ``pdftotext -layout`` (poppler). Não substitui
``crawler/extract.py``; serve para (a) cruzar a extração do Firecrawl com o
PDF (``validate.conferir_com_pdf``) e (b) ser avaliado como extrator padrão.

Layout Cebraspe (duas colunas)::

    13 No Windows, um arquivo pode estar …     |  29 Nos termos da teoria …
         volumes.                              |       Penal brasileiro, …
    A respeito de …, julgue os itens …         |     A autoridade policial …

- o número do item fica na borda da coluna; a continuação vem recuada
  (2–6 espaços); comando ("julgue os itens…") e texto-base ficam na borda,
  parágrafos de texto-base começam com recuo ≥ 7 → ambos encerram o item;
- ``-layout`` deixa linhas em branco no meio de um item (sobra da outra
  coluna), então linha em branco NÃO encerra item;
- só são aceitos números de item que existem no gabarito, em ordem
  crescente (evita confundir instruções numeradas e numeração de linha do
  texto-base com itens); linha só com um número é ignorada.

Convenção do dataset: enunciado = só o texto do item (sem texto-base nem
comando).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

from .gabarito import pdf_to_text
from .models import ProvaExtraida, QuestaoExtraida

GAP_MIN = 2            # espaços que separam as colunas numa linha
CONT_MIN, CONT_MAX = 2, 7
MAX_RECUO_ITEM = 7         # nº de item desalinhado pelo -layout
MAX_LINHAS_EMBUTIDAS = 40  # tabela/código/lista dentro de um item

_HEADER = re.compile(r"^\s*(CEBRASPE\s+[–—-]|Espa[çc]o\s+livre\s*$)", re.I)
_ITEM = re.compile(r"^(\d{1,3})\s+(\S.*)$")
_LONE_NUM = re.compile(r"^\s*\d{1,3}\s*$")


# ---------------------------------------------------------------------------
# Colunas
# ---------------------------------------------------------------------------

def inicio_coluna_direita(linhas: list[str]) -> Optional[int]:
    """Posição (em caracteres) onde começa a coluna direita da página."""
    largura = max((len(l) for l in linhas), default=0)
    if largura < 60:
        return None
    lo, hi = int(largura * 0.3), int(largura * 0.8)
    pos: Counter[int] = Counter()
    for l in linhas:
        for m in re.finditer(r" {%d,}(?=\S)" % GAP_MIN, l):
            p = m.end()
            if lo <= p <= hi:
                pos[p] += 1
        # linha que só tem a coluna direita
        m = re.match(r"^ +(?=\S)", l)
        if m and lo <= m.end() <= hi:
            pos[m.end()] += 1
    if not pos:
        return None
    # margem da coluna: muitas linhas começam em p ou logo depois (recuo de
    # continuação), e quase nenhuma linha tem texto atravessando p
    # (tabelas/texto centralizado na coluna esquerda geram falsos inícios)
    melhor, melhor_score = None, 0
    for p, c in pos.items():
        if c < 2:
            continue
        janela = sum(pos[q] for q in range(p, p + CONT_MAX + 2))
        cruza = sum(1 for l in linhas if len(l) > p and l[p - 1] != " " and l[p] != " ")
        score = janela - 3 * cruza
        if score > melhor_score or (score == melhor_score and melhor is not None and p < melhor):
            melhor, melhor_score = p, score
    return melhor if melhor_score >= 3 else None


def dividir_linha(linha: str, r: int) -> tuple[str, str]:
    if len(linha) <= r:
        return linha, ""
    if linha[r - 1] == " " and (r < 2 or linha[r - 2] == " " or linha[:r].strip() == ""):
        return linha[:r], linha[r:]
    # texto da esquerda invade a calha: corta no vão mais próximo
    for d in range(1, 16):
        for c in (r - d, r + d):
            if GAP_MIN <= c < len(linha) and linha[c - GAP_MIN:c] == " " * GAP_MIN \
                    and linha[c] != " ":
                # preserva o recuo relativo da coluna direita
                return linha[:c], " " * max(0, c - r) + linha[c:]
    return linha, ""  # linha de largura total (instruções da capa etc.)


def linhas_em_ordem(texto: str) -> list[str]:
    """Linhas na ordem de leitura: por página, coluna esquerda e depois a direita."""
    saida: list[str] = []
    for pagina in texto.split("\f"):
        linhas = [l.rstrip() for l in pagina.splitlines()]
        linhas = [l for l in linhas if not _HEADER.match(l)]
        r = inicio_coluna_direita(linhas)
        if r is None:
            saida.extend(linhas)
            continue
        esq, dir_ = [], []
        for l in linhas:
            a, b = dividir_linha(l, r)
            # o cabeçalho "CEBRASPE – …" costuma dividir a linha com a outra coluna
            esq.append("" if _HEADER.match(a) else a.rstrip())
            dir_.append("" if _HEADER.match(b) else b.rstrip())
        saida.extend(esq)
        saida.extend(dir_)
    return saida


# ---------------------------------------------------------------------------
# Itens
# ---------------------------------------------------------------------------

def _juntar(partes: list[str]) -> str:
    out = ""
    for p in partes:
        p = re.sub("[-]", " ", p).strip()  # marcadores da fonte Symbol (PUA)
        if not p:
            continue
        if not out:
            out = p
        elif re.search(r"[^\W\d_]-$", out) and re.match(r"[a-zà-ú]", p):
            out += p                        # "impedi-" + "los" → "impedi-los"
        else:
            out += " " + p
    return re.sub(r"\s+", " ", out).strip()


# Todo texto-base/comando da Cebraspe termina num comando "julgue …" antes do
# próximo item ("jugue" aparece com erro de digitação nas provas; a seção de
# inglês usa "judge"); uma citação de fonte também indica texto-base.
_FIM_DE_ITEM = re.compile(r"\bj[uú]l?gue\b|\bjudge\b|com adapta[çc][õo]es\)", re.I)


def itens_do_texto(texto: str, esperados: Optional[Iterable[int]] = None) -> dict[int, str]:
    """numero → texto do item. ``esperados`` = itens do gabarito (recomendado).

    Linha com recuo de continuação (2–7) → continua o item. Qualquer outra linha
    (na borda ou muito recuada: tabela, código, lista, fórmula, ou continuação
    desalinhada pelo -layout) só encerra o item se, até o próximo item, aparecer
    um comando "julgue" ou citação de fonte; senão faz parte do item.
    """
    esperado = sorted(set(esperados)) if esperados else None
    linhas = []
    for linha in linhas_em_ordem(texto):
        if linha.strip() and not _LONE_NUM.match(linha):
            linhas.append((len(linha) - len(linha.lstrip(" ")), linha.strip()))

    itens: dict[int, list[str]] = {}
    atual: Optional[int] = None
    ultimo = 0

    def aceita(i: int, ultimo: int) -> Optional[int]:
        """Número do item que começa na linha i, ou None."""
        recuo, corpo = linhas[i]
        m = _ITEM.match(corpo)
        if not m or recuo > MAX_RECUO_ITEM:
            return None
        n = int(m.group(1))
        if n <= ultimo:
            return None
        if recuo <= 1:
            ok = n in esperado if esperado else (n == ultimo + 1 or ultimo == 0)
        else:  # número desalinhado pelo -layout: só o próximo item esperado
            prox = [x for x in esperado if x > ultimo][:1] if esperado else [ultimo + 1]
            ok = bool(prox) and n == prox[0]
        return n if ok else None

    def inicio_paragrafo(k: int) -> bool:
        """Primeira linha de parágrafo de texto-base: recuo ≥ 8, maiúscula, e a
        linha seguinte volta para a borda."""
        recuo, corpo = linhas[k]
        return (recuo > CONT_MAX and corpo[:1].isupper() and k + 1 < len(linhas)
                and linhas[k + 1][0] <= 1)

    def encerra(i: int) -> bool:
        """A partir da linha i, há comando/citação antes do próximo item?"""
        if inicio_paragrafo(i):
            return True
        fim = i + MAX_LINHAS_EMBUTIDAS
        for k in range(i, min(len(linhas), fim)):
            if aceita(k, ultimo) is not None:
                return False
            if _FIM_DE_ITEM.search(linhas[k][1]):
                return True
            if k > i and inicio_paragrafo(k):
                return False  # texto-base começa depois: as linhas até aqui são do item
        # fim da prova sem comando: ainda é o último item; bloco longo demais: texto-base
        return len(linhas) >= fim

    for i, (recuo, corpo) in enumerate(linhas):
        n = aceita(i, ultimo)
        if n is not None:
            atual = ultimo = n
            itens[n] = [_ITEM.match(corpo).group(2)]
            continue
        if atual is None:
            continue
        if CONT_MIN <= recuo <= CONT_MAX or not encerra(i):
            itens[atual].append(corpo)
            continue
        atual = None  # comando ou texto-base: o item acabou
    return {n: _juntar(p) for n, p in itens.items()}


_ILEGIVEL = re.compile("[\u0590-\u08FF\u0D80-\u0DFF\u202A-\u202E\uFB1D-\uFDFF\uFE70-\uFEFF]")  # hebraico/árabe/siríaco/cingalês: glifos de fórmula


def ilegiveis(itens: dict[int, str]) -> list[int]:
    """Itens com glifos de fórmula sem mapeamento Unicode (precisam de fallback)."""
    return sorted(n for n, t in itens.items() if _ILEGIVEL.search(t))


def itens_do_pdf(pdf: Path, esperados: Optional[Iterable[int]] = None) -> dict[int, str]:
    return itens_do_texto(pdf_to_text(pdf), esperados)


def extrair(pdf: Path, esperados: Iterable[int]) -> ProvaExtraida:
    """ProvaExtraida (certo/errado) a partir do PDF, sem Firecrawl."""
    itens = itens_do_pdf(pdf, esperados)
    return ProvaExtraida(questoes=[
        QuestaoExtraida(numero=n, enunciado=t, alternativas=["Certo", "Errado"])
        for n, t in sorted(itens.items())
    ])
