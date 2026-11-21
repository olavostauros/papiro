"""Validação de uma prova extraída contra o gabarito definitivo.

Prova **reprovada não entra no dataset**. Erros (reprovam):

- numeração duplicada ou com buracos;
- itens do gabarito ausentes na extração, ou itens extraídos fora do gabarito
  (o total de questões tem que bater com o gabarito);
- enunciado vazio;
- gabarito ausente/inválido para um item não anulado;
- tipo incompatível (gabarito C/E com alternativas de múltipla escolha, ou
  vice-versa).

Com ``itens_pdf`` (texto de cada item segundo o parser local sobre
``pdftotext``), também reprovam: renumeração (enunciado do item N é o texto do
item M do PDF), item pulado e enunciado que não confere com o PDF — mesmo que
a contagem feche.

Avisos (não reprovam, mas vão para o relatório): enunciado muito longo
(provável texto-base colado — a convenção do dataset é só o item),
alternativas de múltipla escolha fora de 4–5, avisos do parser do gabarito.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Iterable, Optional

from .gabarito import Gabarito
from .models import ProvaExtraida, infer_tipo

ENUNCIADO_LONGO = 1200  # caracteres


@dataclass
class Relatorio:
    caderno: str
    url_prova: str
    url_gabarito: str
    aprovada: bool = False
    total_extraido: int = 0
    total_gabarito: int = 0
    anulados: list[int] = field(default_factory=list)
    registros_validos: int = 0        # itens que viram registro (sem anulados)
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _faixas(nums: list[int]) -> str:
    """[1,2,3,7,9,10] → '1–3, 7, 9–10'."""
    if not nums:
        return "—"
    nums = sorted(nums)
    out, ini, prev = [], nums[0], nums[0]
    for n in nums[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        out.append(f"{ini}–{prev}" if prev != ini else f"{ini}")
        if n is not None:
            ini = prev = n
    return ", ".join(out)


def validar(prova: ProvaExtraida, gab: Gabarito, *, caderno: str = "",
            url_prova: str = "", url_gabarito: str = "",
            itens_pdf: Optional[dict[int, str]] = None) -> Relatorio:
    """``itens_pdf`` (numero → texto do item, de ``extract_local.itens_do_pdf``)
    liga o cruzamento com o PDF: renumeração ou item pulado reprovam."""
    r = Relatorio(caderno=caderno, url_prova=url_prova,
                  url_gabarito=url_gabarito or gab.url)
    nums = [q.numero for q in prova.questoes]
    r.total_extraido = len(nums)
    r.total_gabarito = len(gab.itens)
    r.anulados = gab.anulados
    r.avisos.extend(f"gabarito: {a}" for a in gab.avisos)

    if not nums:
        r.erros.append("nenhuma questão extraída")
        return r

    dup = sorted(n for n, c in Counter(nums).items() if c > 1)
    if dup:
        r.erros.append(f"numeração duplicada: {_faixas(dup)}")
    uniq = sorted(set(nums))
    buracos = sorted(set(range(uniq[0], uniq[-1] + 1)) - set(uniq))
    if buracos:
        r.erros.append(f"buracos na numeração: {_faixas(buracos)}")

    esperados = set(gab.itens)
    faltando = sorted(esperados - set(uniq))
    sobrando = sorted(set(uniq) - esperados)
    if faltando:
        r.erros.append(f"itens do gabarito ausentes na extração: {_faixas(faltando)}")
    if sobrando:
        r.erros.append(f"itens extraídos fora do gabarito: {_faixas(sobrando)}")
    if len(nums) != len(esperados) and not (dup or faltando or sobrando):
        r.erros.append(f"total extraído {len(nums)} ≠ gabarito {len(esperados)}")

    tipo_gab = gab.tipo
    vazios, sem_gab, tipo_ruim, longos, alt_ruins = [], [], [], [], []
    validos = 0
    for q in prova.questoes:
        if not (q.enunciado or "").strip():
            vazios.append(q.numero)
        if q.numero not in esperados:
            continue
        if q.numero in gab.anulados:
            continue
        tipo_q = infer_tipo(q.alternativas)
        if tipo_q != tipo_gab:
            tipo_ruim.append(q.numero)
            continue
        if gab.para_dataset(q.numero, tipo_q) is None:
            sem_gab.append(q.numero)
            continue
        if len(q.enunciado or "") > ENUNCIADO_LONGO:
            longos.append(q.numero)
        if tipo_q == "multipla_escolha" and not 4 <= len(q.alternativas) <= 5:
            alt_ruins.append(q.numero)
        validos += 1

    if vazios:
        r.erros.append(f"enunciado vazio: {_faixas(vazios)}")
    if sem_gab:
        r.erros.append(f"gabarito ausente/inválido: {_faixas(sem_gab)}")
    if tipo_ruim:
        r.erros.append(f"tipo incompatível com o gabarito ({tipo_gab}): {_faixas(tipo_ruim)}")
    if longos:
        r.avisos.append(f"enunciado > {ENUNCIADO_LONGO} caracteres (texto-base colado?): "
                        f"{_faixas(longos)}")
    if alt_ruins:
        r.avisos.append(f"múltipla escolha com nº de alternativas fora de 4–5: "
                        f"{_faixas(alt_ruins)}")

    if itens_pdf is not None:
        conferir_com_pdf(prova, itens_pdf, r, esperados=gab.itens)

    r.registros_validos = validos
    r.aprovada = not r.erros
    return r


# ---------------------------------------------------------------------------
# Cruzamento com o texto do PDF (pdftotext, grátis)
# ---------------------------------------------------------------------------

COBERTURA_MINIMA = 0.5   # abaixo disso o parser local falhou no layout: só avisa
PREFIXO = 40             # caracteres (normalizados) comparados
SIMILAR = 0.8


def _chave(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def confere(extraido: str, do_pdf: str) -> bool:
    """O enunciado extraído corresponde ao texto do item no PDF?

    Aceita enunciado com texto-base/comando antes do item (o PROMPT do
    extract_prova pede isso) e enunciado que traz só a parte final do item.
    """
    e, p = _chave(extraido), _chave(do_pdf)
    if not e or not p:
        return False
    if p[:PREFIXO] in e or e[:PREFIXO] in p:
        return True
    return difflib.SequenceMatcher(None, e[:2 * PREFIXO], p[:2 * PREFIXO]).ratio() >= SIMILAR


def conferir_com_pdf(prova: ProvaExtraida, itens_pdf: dict[int, str], r: Relatorio,
                     esperados: Optional[Iterable[int]] = None) -> None:
    """Reprova renumeração e item pulado, mesmo que a contagem feche."""
    esperados = sorted(set(esperados or itens_pdf))
    cobertura = len(set(itens_pdf) & set(esperados)) / max(1, len(esperados))
    if cobertura < COBERTURA_MINIMA:
        r.avisos.append(f"cruzamento com o PDF não aplicado: parser local achou só "
                        f"{cobertura:.0%} dos itens (layout não suportado)")
        return
    renumerados, nao_conferem, sem_pdf = [], [], []
    casados: set[int] = set()     # itens do PDF cujo texto apareceu na extração
    for q in prova.questoes:
        texto_pdf = itens_pdf.get(q.numero)
        if texto_pdf is None:
            sem_pdf.append(q.numero)
            continue
        if confere(q.enunciado, texto_pdf):
            casados.add(q.numero)
            continue
        outro = next((m for m, t in itens_pdf.items() if m != q.numero and confere(q.enunciado, t)),
                     None)
        if outro is not None:
            renumerados.append(f"{q.numero}→{outro}")
            casados.add(outro)
        else:
            nao_conferem.append(q.numero)
    if renumerados:
        r.erros.append("renumeração: item extraído ≠ item do PDF (extraído→PDF): "
                       + ", ".join(renumerados))
    if nao_conferem:
        r.erros.append(f"enunciado não confere com o texto do item no PDF: {_faixas(nao_conferem)}")
    if sem_pdf:
        r.avisos.append(f"itens não localizados pelo parser local (sem cruzamento): "
                        f"{_faixas(sem_pdf)}")
    pulados = sorted((set(itens_pdf) & set(esperados)) - casados - set(nao_conferem))
    if pulados and renumerados:
        r.erros.append(f"itens do PDF pulados pela extração: {_faixas(pulados)}")


def formatar(r: Relatorio) -> str:
    status = "APROVADA" if r.aprovada else "REPROVADA"
    linhas = [
        f"[{status}] {r.caderno}",
        f"  prova:    {r.url_prova}",
        f"  gabarito: {r.url_gabarito}",
        f"  extraídas {r.total_extraido} | gabarito {r.total_gabarito} | "
        f"anulados {len(r.anulados)} ({_faixas(r.anulados)}) | registros {r.registros_validos}",
    ]
    linhas += [f"  ERRO:  {e}" for e in r.erros]
    linhas += [f"  aviso: {a}" for a in r.avisos]
    return "\n".join(linhas)
