"""Validação de uma prova extraída contra o gabarito definitivo.

Prova **reprovada não entra no dataset**. Erros (reprovam):

- numeração duplicada ou com buracos;
- itens do gabarito ausentes na extração, ou itens extraídos fora do gabarito
  (o total de questões tem que bater com o gabarito);
- enunciado vazio;
- gabarito ausente/inválido para um item não anulado;
- tipo incompatível (gabarito C/E com alternativas de múltipla escolha, ou
  vice-versa).

Avisos (não reprovam, mas vão para o relatório): enunciado muito longo
(provável texto-base colado — a convenção do dataset é só o item),
alternativas de múltipla escolha fora de 4–5, avisos do parser do gabarito.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

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
            url_prova: str = "", url_gabarito: str = "") -> Relatorio:
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

    r.registros_validos = validos
    r.aprovada = not r.erros
    return r


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
