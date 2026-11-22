"""CLI for the zero-credit Cebraspe ingestion loop. See package docstring."""
import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from crawler.cebraspe import api  # noqa: E402
from crawler.cebraspe.gabarito import parse_gabarito, report as gab_report  # noqa: E402
from crawler.cebraspe.pipeline import assemble, parse_items  # noqa: E402
from crawler.shards import SHARD_DIR  # noqa: E402

JOBS_DIR = Path(__file__).resolve().parents[2] / "crawler/jobs"


def slug(s):
    a = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", a.lower())).strip("-")


def done_eventos():
    # shard filenames are the Cebraspe eventoURL (EXTERNO_* shards never match)
    return {p.stem for p in SHARD_DIR.glob("*.json")}


def cmd_next(args):
    done = done_eventos()
    evs = sorted(api.list_eventos(),
                 key=lambda e: (-e["eventoAno"],
                                -(int(e["eventoTotalVagas"] or 0))))
    shown = probed = 0
    for e in evs:
        if e["eventoURL"] in done:
            continue
        status = ""
        if args.probe:
            try:
                det = api.get_evento(e["idEvento"])
                nprov = sum(1 for a in det.get("arquivosGabarito") or []
                            if api.arquivo_kind(a) == "prova")
                ngab = sum(1 for a in det.get("arquivosGabarito") or []
                           if api.arquivo_kind(a) == "gabarito")
                status = f"provas={nprov} gabaritos={ngab}"
                probed += 1
                if not nprov:
                    continue
            except Exception as ex:
                status = f"detail error: {ex}"
        print(f'{e["eventoAno"]} vagas={(e["eventoTotalVagas"] or 0):>6} '
              f'{e["eventoURL"]}  {(e["eventoNomeAbreviado"] or "")[:45]}  {status}')
        shown += 1
        if shown >= args.limit or probed >= args.probe:
            break


def cmd_files(args):
    det = api.get_evento(args.evento)
    print(det["eventoNomeAbreviado"], "|", det["eventoNomeCompleto"],
          "| ano:", det["eventoAno"], "| vagas:", det["eventoTotalVagas"])
    print("\n== CARGOS ==")
    for c in det.get("eventoCargos") or []:
        print(f'  {c["idArea"]}: {c["area"]}')
    print("\n== ARQUIVOS ==")
    for a in det.get("arquivosGabarito") or []:
        kind = api.arquivo_kind(a)
        cargos = ",".join(api.arquivo_cargos(a))
        print(f'  [{kind:8}] {a["nomeArquivo"]}  cargos={cargos or "-"}')
        print(f'             {(a.get("descricaoArquivo") or "")[:90]}')


def _key_for(nome):
    """Short local key from a CDN filename: 106_PF_CB1_01.pdf -> CB1,
    GAB_DEFINITIVO_378_ABIN_015_07.PDF -> 015_07, hash.pdf -> hash[:12]."""
    b = re.sub(r"\.pdf$", "", Path(nome).name, flags=re.I)
    b = re.sub(r"^(GAB(_DEFINITIVO)?_|MATRIZ_|ED_PROVA_|RESPOSTA_DEFINITIVA_)", "",
               b, flags=re.I)
    b = re.sub(r"_PAG_\d+$|_ADAPTADA$|_RESPOSTA.*$", "", b, flags=re.I)
    parts = b.split("_")
    # drop leading numeric seq and event-name parts
    while parts and (parts[0].isdigit() or parts[0].upper()
                     in {"PF", "PRF", "IBAMA", "ABIN", "BANRISUL"}):
        parts.pop(0)
    b = "_".join(parts) or b
    return re.sub(r"[^A-Za-z0-9_]", "_", b)[:24] or "f"


def cmd_fetch(args):
    det = api.get_evento(args.evento)
    evento = det["eventoURL"]
    workdir = Path(args.workdir or
                   f"{os.environ.get('PAPIRO_WORKDIR', '/tmp')}/{evento.lower()}")
    workdir.mkdir(parents=True, exist_ok=True)
    arqs = [a for a in det.get("arquivosGabarito") or []
            if api.arquivo_kind(a) in ("prova", "gabarito")]
    manifest = {}
    for a in arqs:
        kind = api.arquivo_kind(a)
        key = _key_for(a["nomeArquivo"])
        local = f"{kind[:3]}_{key}.pdf"
        i = 2
        while local in manifest.values():
            local = f"{kind[:3]}_{key}_{i}.pdf"
            i += 1
        dest = workdir / local
        if not dest.exists():
            api.download(evento, a["nomeArquivo"], dest)
        manifest[a["nomeArquivo"]] = local
        print(f"{kind:8} {local}  <- {a['nomeArquivo']}")
    # job skeleton
    cargos = [{"idArea": c["idArea"], "cargo": re.sub(r"^CARGO\s*\d+\s*[:-]?\s*", "", c["area"]).strip(),
               "id_cargo": slug(re.sub(r"^CARGO\s*\d+\s*[:-]?\s*", "", c["area"]))[:40],
               "provas": []}
              for c in det.get("eventoCargos") or []]
    provas = {a["nomeArquivo"]: a for a in arqs if api.arquivo_kind(a) == "prova"}
    gabs = {a["nomeArquivo"]: a for a in arqs if api.arquivo_kind(a) == "gabarito"}
    unmatched = []
    for nome, a in provas.items():
        cids = api.arquivo_cargos(a)
        entry = {"key": _key_for(nome), "prova": manifest[nome],
                 "gabarito": "", "tipo": "ce", "arquivo": nome}
        for gnome, g in gabs.items():
            if api.arquivo_cargos(g) == cids:
                entry["gabarito"] = manifest[gnome]
        targets = [c for c in cargos if c["idArea"].lstrip("0") in
                   {x.lstrip("0") for x in cids}]
        if targets:
            for t in targets:
                t["provas"].append(dict(entry))
        else:
            unmatched.append(entry)
    job = {"evento": evento, "workdir": str(workdir),
           "meta": {"banca": "Cebraspe", "orgao": det["eventoNomeCompleto"] or det["eventoNomeAbreviado"],
                    "ano": det["eventoAno"], "id_orgao": slug(evento.split("_")[0])},
           "cargos": cargos, "unmatched": unmatched,
           "variant": "modern", "skip": {}, "patch": {}}
    (workdir / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1))
    print(f"\njob skeleton -> {workdir}/job.json  "
          f"({len(cargos)} cargos, {len(unmatched)} unmatched provas)")


def cmd_audit(args):
    workdir = Path(args.workdir)
    job_path = workdir / "job.json"
    if job_path.exists():
        job = json.loads(job_path.read_text())
        seen = {}
        for c in job["cargos"]:
            for p in c["provas"]:
                seen[p["key"]] = p
        for p in job.get("unmatched", []):
            seen[p["key"]] = p
        entries = list(seen.values())
    else:
        entries = [{"key": f.stem, "prova": f.name, "gabarito": "", "tipo": "ce"}
                   for f in sorted(workdir.glob("*.pdf"))]
    for p in entries:
        pdf = workdir / p["prova"]
        if not pdf.exists():
            continue
        if p.get("gabarito") and (workdir / p["gabarito"]).exists():
            gab = parse_gabarito(str(workdir / p["gabarito"]))
            print(f"== {p['key']}  gabarito: {gab_report(gab)}")
        tipo = args.tipo or p.get("tipo", "ce")
        try:
            its, dropped = parse_items(pdf, tipo, job.get("variant", "modern")
                                       if job_path.exists() else "modern",
                                       audit=True)
        except Exception as ex:
            print(f"   {p['key']}: PARSE FAIL {ex}")
            continue
        alts = sum(len(v["alternativas"]) for v in its.values())
        print(f"   {p['key']} [{tipo}]: {len(its)} items, {alts} alternativas, "
              f"{len(dropped)} dropped lines -> dropped_{p['key']}.txt")
        (workdir / f"dropped_{p['key']}.txt").write_text(
            "\n".join(f"p{pg} c{c} {t}" for pg, c, t in dropped))
        if p.get("gabarito") and (workdir / p["gabarito"]).exists():
            missing = [n for n in sorted(gab) if gab[n] != "X" and n not in its]
            if missing:
                print(f"   ! gabarito items not parsed: {missing}")


def cmd_assemble(args):
    assemble(Path(args.workdir) / "job.json", write=args.write)


def main():
    ap = argparse.ArgumentParser(prog="python -m crawler.cebraspe")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("next")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--probe", type=int, default=0,
                   help="fetch details for up to N candidates")
    p.set_defaults(fn=cmd_next)
    p = sub.add_parser("files")
    p.add_argument("evento")
    p.set_defaults(fn=cmd_files)
    p = sub.add_parser("fetch")
    p.add_argument("evento")
    p.add_argument("--workdir")
    p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("audit")
    p.add_argument("--workdir", required=True)
    p.add_argument("--tipo", choices=["ce", "mc"])
    p.set_defaults(fn=cmd_audit)
    p = sub.add_parser("assemble")
    p.add_argument("--workdir", required=True)
    p.add_argument("--write", action="store_true")
    p.set_defaults(fn=cmd_assemble)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
