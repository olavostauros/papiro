"""Benchmark do extrator local contra o dataset (somente leitura, zero crédito).

Para cada prova: itens esperados (gabarito), extraídos localmente, quantos
enunciados batem EXATAMENTE com o dataset, quantos batem após normalização
leve (espaços, aspas, espaço antes de pontuação) e as divergências.

Provas sem referência no dataset (ex.: CD_26_PL) são comparadas com a
extração Firecrawl em cache, quando houver.

    python -m crawler.bench_local --evento PF_25 --caderno 6BA6C911…
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import discover, extract_local, gabarito as gabmod
from .models import ProvaExtraida

HERE = Path(__file__).resolve().parent
EXTRACOES = HERE / ".cache" / "extracoes"


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").replace("*", "")
    s = re.sub(r"[“”„\"]", '"', s)
    s = re.sub(r"[‘’`]", "'", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([.,;:!?)\]])", r"\1", s)
    s = re.sub(r"([(\[])\s+", r"\1", s)
    s = re.sub(r'"\s+(?=[^"]*"(?:\s|$))', '"', s)   # aspas com espaço interno
    return s


def referencia_dataset(dataset: list[dict], url: str) -> dict[int, str]:
    ref: dict[int, str] = {}
    for q in dataset:
        if q["fonte"].lower() == url.lower():
            n = int(q["id"].rsplit("-", 1)[1])
            ref.setdefault(n, q["enunciado"])
    return ref


def referencia_firecrawl(e: dict) -> dict[int, str]:
    p = EXTRACOES / e["evento"] / f"{e['caderno']}.json"
    if not p.exists():
        return {}
    prova = ProvaExtraida.model_validate_json(p.read_text(encoding="utf-8"))
    return {q.numero: q.enunciado for q in prova.questoes}


def _trechos_divergentes(a: str, b: str) -> tuple[list[str], list[str]]:
    """Trechos (por palavra) só em a e só em b."""
    wa, wb = a.split(), b.split()
    so_a, so_b = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb).get_opcodes():
        if op in ("replace", "delete"):
            so_a.append(" ".join(wa[max(0, i1 - 1):i2 + 1]))
        if op in ("replace", "insert"):
            so_b.append(" ".join(wb[max(0, j1 - 1):j2 + 1]))
    return so_a, so_b


def classificar(local: str, ref: str, pdf_plano: str) -> str:
    nl, nr = normalizar(local), normalizar(ref)
    if extract_local.ilegiveis({0: local}):
        return "fórmula ilegível no local"
    if nl.startswith(nr):
        return "local com texto a mais"
    if nr.startswith(nl):
        return "local truncado"
    so_ref, so_local = _trechos_divergentes(nr, nl)
    no_pdf = lambda t: normalizar(t) in pdf_plano
    if so_ref and all(not no_pdf(t) for t in so_ref) and all(no_pdf(t) for t in so_local):
        return "erro na referência (trecho não existe no PDF)"
    return "outro"


def comparar(local: dict[int, str], ref: dict[int, str], pdf_plano: str = "") -> dict:
    exato, norm, div = 0, 0, []
    for n, r in sorted(ref.items()):
        l = local.get(n)
        if l is None:
            div.append({"item": n, "tipo": "ausente no local", "ref": r[:300], "local": None})
        elif l == r:
            exato += 1
        elif normalizar(l) == normalizar(r):
            norm += 1
        else:
            div.append({"item": n, "tipo": classificar(l, r, pdf_plano),
                        "ref": r[:300], "local": l[:300]})
    return {"exato": exato, "normalizado": norm, "divergencias": div}


def pdf_plano(pdf: Path) -> str:
    """Texto corrido do PDF (sem -layout), para conferir trechos."""
    import subprocess
    out = subprocess.run([gabmod.pdftotext_bin(), "-enc", "UTF-8", str(pdf), "-"],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    out = re.sub(r"-\n(?=\w)", "-", out)
    return normalizar(out)


def bench(entradas: list[dict], dataset: list[dict]) -> list[dict]:
    linhas = []
    for e in entradas:
        gab = gabmod.carregar(e["url_gabarito"])
        pdf = gabmod.baixar(e["url_prova"])
        local = extract_local.itens_do_pdf(pdf, gab.itens)
        validos = [n for n in gab.itens if n not in gab.anulados]
        ref = referencia_dataset(dataset, e["url_prova"])
        fonte_ref = "dataset"
        if not ref:
            ref, fonte_ref = referencia_firecrawl(e), "firecrawl (cache)"
        # o dataset não tem anulados; compara só itens válidos
        ref = {n: t for n, t in ref.items() if n in validos}
        c = comparar(local, ref, pdf_plano(pdf))
        linhas.append({
            "evento": e["evento"], "caderno": e["caderno"], "referencia": fonte_ref,
            "esperados": len(gab.itens), "anulados": len(gab.anulados),
            "extraidos": len(local), "faltando_local": sorted(set(gab.itens) - set(local)),
            "na_referencia": len(ref), "ilegiveis": extract_local.ilegiveis(local), **c,
        })
    return linhas


def tabela(linhas: list[dict]) -> str:
    out = ["| prova | ref. | esperados | extraídos | na ref. | exatos | só normalização "
           "| divergem | erro na ref. | fórmula | local a mais | local truncado | ausente | outro |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    cats = [("erro na referência", "ref"), ("fórmula", "form"), ("texto a mais", "mais"),
            ("truncado", "trunc"), ("ausente", "aus"), ("outro", "outro")]
    tot = dict(esperados=0, extraidos=0, na_referencia=0, exato=0, normalizado=0, div=0)
    tot.update({k: 0 for _, k in cats})
    for l in linhas:
        cad = l["caderno"] if len(l["caderno"]) <= 16 else l["caderno"][:10] + "…"
        nd = len(l["divergencias"])
        por = {k: sum(1 for d in l["divergencias"] if chave in d["tipo"]) for chave, k in cats}
        out.append(f"| {l['evento']}/{cad} | {l['referencia']} | {l['esperados']} | "
                   f"{l['extraidos']} | {l['na_referencia']} | {l['exato']} | "
                   f"{l['normalizado']} | {nd} | " + " | ".join(str(por[k]) for _, k in cats) + " |")
        for k in por:
            tot[k] += por[k]
        for k in ("esperados", "extraidos", "na_referencia"):
            tot[k] += l[k]
        tot["exato"] += l["exato"]; tot["normalizado"] += l["normalizado"]; tot["div"] += nd
    out.append(f"| **total** | | {tot['esperados']} | {tot['extraidos']} | {tot['na_referencia']} "
               f"| {tot['exato']} | {tot['normalizado']} | {tot['div']} | "
               + " | ".join(str(tot[k]) for _, k in cats) + " |")
    return "\n".join(out)


def cobertura(entradas: list[dict], dataset: Optional[list[dict]] = None) -> list[dict]:
    """Sem referência de texto: valida pela contagem e pelo gabarito."""
    linhas = []
    for e in entradas:
        base = {"evento": e["evento"], "caderno": e["caderno"], "ano": e.get("ano"),
                "arquivo": e["url_prova"].rsplit("/", 1)[1]}
        try:
            gab = gabmod.carregar(e["url_gabarito"])
        except Exception as exc:  # noqa: BLE001
            linhas.append({**base, "status": f"gabarito ilegível: {exc}"[:120]})
            continue
        if gab.tipo != "certo_errado":
            linhas.append({**base, "esperados": len(gab.itens), "status": "múltipla escolha (fora)"})
            continue
        try:
            local = extract_local.itens_do_pdf(gabmod.baixar(e["url_prova"]), gab.itens)
        except Exception as exc:  # noqa: BLE001
            linhas.append({**base, "esperados": len(gab.itens), "status": f"erro: {exc}"[:120]})
            continue
        achados = set(local) & set(gab.itens)
        cob = len(achados) / max(1, len(gab.itens))
        ileg = extract_local.ilegiveis(local)
        linha = {**base, "esperados": len(gab.itens), "anulados": len(gab.anulados),
                 "extraidos": len(achados), "cobertura": round(cob, 4),
                 "faltando": sorted(set(gab.itens) - achados), "ilegiveis": ileg,
                 "status": "ok" if cob == 1 else "cobertura incompleta → fallback da prova"}
        if dataset is not None:   # informação extra, quando houver referência
            validos = set(gab.itens) - set(gab.anulados)
            ref = {n: t for n, t in referencia_dataset(dataset, e["url_prova"]).items()
                   if n in validos}
            if ref:
                iguais = sum(1 for n, t in ref.items()
                             if n in local and normalizar(local[n]) == normalizar(t))
                linha["iguais_dataset"] = f"{iguais}/{len(ref)}"
        linhas.append(linha)
    return linhas


def tabela_cobertura(linhas: list[dict]) -> str:
    out = ["| evento (ano) | arquivo | gabarito | extraídos | cobertura | ilegíveis | faltando "
           "| iguais ao dataset | status |", "|---|---|---:|---:|---:|---:|---|---:|---|"]
    for l in linhas:
        cob = f"{l['cobertura']:.0%}" if "cobertura" in l else "—"
        falt = l.get("faltando") or []
        falt_s = (", ".join(map(str, falt[:6])) + ("…" if len(falt) > 6 else "")) if falt else "—"
        out.append(f"| {l['evento']} ({l.get('ano')}) | {l['arquivo'][:34]} | {l.get('esperados', '—')} "
                   f"| {l.get('extraidos', '—')} | {cob} | {len(l.get('ilegiveis', []))} | {falt_s} "
                   f"| {l.get('iguais_dataset', '—')} | {l['status']} |")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="benchmark do extrator local (zero crédito)")
    ap.add_argument("--evento", action="append", default=[])
    ap.add_argument("--caderno", action="append", default=[])
    ap.add_argument("--exemplos", type=int, default=3)
    ap.add_argument("--cobertura", action="store_true",
                    help="sem referência de texto: só contagem/gabarito por prova")
    args = ap.parse_args(argv)
    if args.cobertura:
        man = json.loads(discover.MANIFEST.read_text(encoding="utf-8"))
        evs = {x.upper() for x in args.evento}
        ents = [e for e in man["provas"] if e.get("url_gabarito") and e.get("fase") == "objetiva"
                and e["evento"].upper() in evs]
        dataset = json.loads(discover.DATASET.read_text(encoding="utf-8"))
        linhas = cobertura(ents, dataset)
        print(tabela_cobertura(linhas))
        out = HERE / "reports" / f"bench-cobertura-{datetime.now():%Y%m%d-%H%M%S}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(linhas, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nrelatório: {out}")
        return 0
    man = json.loads(discover.MANIFEST.read_text(encoding="utf-8"))
    evs = {x.upper() for x in args.evento}
    cads = {x.upper() for x in args.caderno}
    ents = [e for e in man["provas"] if e.get("url_gabarito")
            and (e["evento"].upper() in evs or e["caderno"].upper() in cads)]
    dataset = json.loads(discover.DATASET.read_text(encoding="utf-8"))
    linhas = bench(ents, dataset)
    print(tabela(linhas))
    for l in linhas:
        if l["divergencias"]:
            print(f"\n{l['evento']}/{l['caderno'][:16]} — {len(l['divergencias'])} divergência(s):")
            for d in l["divergencias"][: args.exemplos]:
                print(f"  item {d['item']} [{d['tipo']}]\n    ref:   {d['ref']}\n    local: {d['local']}")
    out = HERE / "reports" / f"bench-local-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(linhas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nrelatório: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
