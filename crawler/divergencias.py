"""Exporta divergências dataset × PDF (de um relatório do bench_local) para Markdown.

    python -m crawler.divergencias crawler/reports/bench-local-….json \
        --saida docs/divergencias-pf2025.md --extra 106_PF_005_01:108

Só lê ``questions.json``; nada é alterado. Entram os casos classificados como
"erro na referência" (trecho do dataset ausente do PDF e trecho do PDF
presente) e os ``--extra`` conferidos manualmente.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from . import discover
from .bench_local import normalizar

NEGACAO = {"não", "nem", "sem", "nunca", "jamais", "nenhum", "nenhuma"}


def _palavras(t: str) -> list[str]:
    return re.findall(r"[\wÀ-ú]+", t.lower())


def vocabulario(dataset: list[dict]) -> Counter:
    """Em quantos enunciados DISTINTOS cada palavra aparece (cadernos
    compartilhados repetem o mesmo enunciado em vários cargos)."""
    voc: Counter = Counter()
    for t in {q["enunciado"] for q in dataset}:
        voc.update(set(_palavras(t)))
    return voc


_SOBRESCRITO = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉", "01234567890123456789")


def so_notacao(ref: str, pdf: str) -> bool:
    """Diferença só de notação (C_2H_6O × C2H6O, n² × n2, x^2 × x2)."""
    f = lambda t: re.sub(r"[_^{}\s]", "", normalizar(t).translate(_SOBRESCRITO))
    return f(ref) == f(pdf)


def pares(ref: str, pdf: str, contexto: int = 2) -> list[tuple[str, str]]:
    """Trechos divergentes (dataset, PDF) por palavra, com contexto dos dois lados."""
    import difflib
    a, b = normalizar(ref).split(), normalizar(pdf).split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        out.append((" ".join(a[max(0, i1 - contexto):i2 + contexto]),
                    " ".join(b[max(0, j1 - contexto):j2 + contexto])))
    return out


def muda_sentido(so_ref: list[str], so_pdf: list[str], voc: Counter) -> str:
    """Heurística documentada no cabeçalho do relatório."""
    ref_w = [w for t in so_ref for w in _palavras(t)]
    pdf_w = [w for t in so_pdf for w in _palavras(t)]
    trocadas_ref = [w for w in ref_w if w not in pdf_w]
    trocadas_pdf = [w for w in pdf_w if w not in ref_w]
    if (set(trocadas_ref) | set(trocadas_pdf)) & NEGACAO:
        return "**sim** (negação)"
    # número: só se os dígitos mudam de fato (subscrito fora de ordem não conta)
    digitos = lambda ts: Counter(ch for t in ts for ch in t if ch.isdigit())
    if digitos(so_ref) != digitos(so_pdf):
        return "**sim** (número)"
    # palavra do dataset que aparece em ≥ 2 outros registros é palavra real:
    # a troca pode mudar o sentido; senão, provável erro de grafia
    if any(voc[w] >= 3 for w in trocadas_ref if len(w) > 2):
        return "possível (palavra trocada por outra)"
    return "não (grafia)"


def _cel(t: str) -> str:
    return t.replace("|", "\\|").replace("\n", " ")


def exportar(relatorio: list[dict], dataset: list[dict], extras: set[tuple[str, int]],
             titulo: str) -> tuple[str, int]:
    voc = vocabulario(dataset)
    por_fonte: dict[str, list[dict]] = {}
    for q in dataset:
        por_fonte.setdefault(q["fonte"].rsplit("/", 1)[1].upper(), []).append(q)
    linhas, notacao = [], []
    for l in relatorio:
        for d in l["divergencias"]:
            chave = (l["caderno"], d["item"])
            if not ("erro na referência" in d["tipo"] or chave in extras):
                continue
            if so_notacao(d["ref"], d["local"]):
                notacao.append(chave)        # convenção de subscrito/expoente, não é erro
                continue
            ps = pares(d["ref"], d["local"])
            so_ref, so_pdf = [p[0] for p in ps], [p[1] for p in ps]
            sentido = muda_sentido(so_ref, so_pdf, voc)
            if chave in extras:
                sentido = sentido.replace("**sim**", "**SIM**") + " — conferido manualmente"
            ids = [q["id"] for q in por_fonte.get(f"{l['caderno']}.PDF", [])
                   if q["id"].endswith(f"-{d['item']:03d}")]
            gabs = sorted({q["gabarito"] for q in por_fonte.get(f"{l['caderno']}.PDF", [])
                           if q["id"].endswith(f"-{d['item']:03d}")})
            linhas.append((l["caderno"], d["item"], " … ".join(so_ref), " … ".join(so_pdf),
                           sentido, len(ids), ids[:1], gabs, chave in extras))
    cont = Counter(x[4].split(" (")[0].replace("**", "").split(" —")[0].lower() for x in linhas)
    out = [
        f"# {titulo}",
        "",
        f"Gerado em {date.today().isoformat()} por `python -m crawler.divergencias` a partir do "
        "benchmark do extrator local (`crawler/bench_local.py`). Nenhum registro do dataset foi "
        "alterado.",
        "",
        "**Critério:** o trecho do dataset **não existe** no texto do PDF oficial "
        "(`pdftotext`) e o trecho correspondente do PDF existe. Casos marcados como "
        "“conferido manualmente” não passaram nesse critério automático e foram verificados "
        "à mão no PDF.",
        "",
        "**Coluna “muda o sentido?” (heurística, revisar):** *sim* quando a diferença envolve "
        "negação (não/nem/sem…) ou número; *possível* quando a palavra do dataset é uma "
        "palavra real (aparece em ≥ 3 registros do dataset) trocada por outra; *não (grafia)* "
        "quando a palavra do dataset não aparece em outros registros — provável erro de "
        "digitação.",
        "",
        f"**Total:** {len(linhas)} itens — " + ", ".join(f"{k}: {v}" for k, v in cont.most_common())
        + (f" (mais {len(notacao)} só de notação, listados ao final)" if notacao else "")
        + ". Como os cadernos de conhecimentos básicos são compartilhados por vários cargos, "
        "cada item pode corresponder a mais de um registro (coluna *registros*).",
        "",
    ]
    destaque = [x for x in linhas if x[8]]
    if destaque:
        out += ["## Destaque", ""]
        for cad, item, ref, pdf, sentido, nreg, ids, gabs, _ in destaque:
            out.append(f"- **{cad} item {item}** (`{ids[0] if ids else '?'}`, gabarito no "
                       f"dataset: **{', '.join(gabs)}**): o dataset diz “{_cel(ref)}”, o PDF diz "
                       f"“{_cel(pdf)}”. {sentido}.")
        out += ["", "## Todos os itens", ""]
    out += ["| prova | item | texto no dataset | texto no PDF | muda o sentido? | registros | exemplo de id |",
            "|---|---:|---|---|---|---:|---|"]
    for cad, item, ref, pdf, sentido, nreg, ids, gabs, dest in linhas:
        marca = "**" if dest else ""
        out.append(f"| {marca}{cad}{marca} | {marca}{item}{marca} | {_cel(ref)} | {_cel(pdf)} | "
                   f"{sentido} | {nreg} | `{ids[0] if ids else '—'}` |")
    if notacao:
        out += ["", f"*Fora da tabela:* {len(notacao)} item(ns) em que a diferença é só de "
                "notação (subscrito/expoente escrito com `_`/`^` no dataset): "
                + ", ".join(f"{c} item {i}" for c, i in notacao) + "."]
    return "\n".join(out) + "\n", len(linhas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("relatorio", type=Path)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--extra", action="append", default=[], help="caderno:item conferido à mão")
    ap.add_argument("--titulo", default="Divergências entre o dataset e o PDF oficial")
    args = ap.parse_args(argv)
    rel = json.loads(args.relatorio.read_text(encoding="utf-8"))
    rel = [l for l in rel if l.get("referencia") == "dataset"]
    dataset = json.loads(discover.DATASET.read_text(encoding="utf-8"))
    extras = set()
    for x in args.extra:
        cad, item = x.rsplit(":", 1)
        extras.add((cad, int(item)))
    md, n = exportar(rel, dataset, extras, args.titulo)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(md, encoding="utf-8")
    print(f"{n} itens → {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
