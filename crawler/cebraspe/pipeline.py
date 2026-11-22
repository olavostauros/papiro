"""Job-driven assemble/audit for the Cebraspe local pipeline.

A job (crawler/jobs/<EVENTO>.json, also copied to the workdir) describes how
prova/gabarito PDFs map onto cargos:

{
  "evento": "BANRISUL_25",
  "meta": {"banca": "Cebraspe", "orgao": "...", "ano": 2025,
           "id_orgao": "banrisul"},
  "cargos": [
    {"cargo": "Técnico em TI II – ...", "id_cargo": "tecnico-ti-...",
     "provas": [
       {"key": "CB1", "prova": "prova_CB1.pdf",
        "gabarito": "gab_CB1.pdf", "tipo": "mc",
        "arquivo": "077_BANRISUL_CB1_01.pdf",
        "assunto": "Conhecimentos Básicos"}
     ]}
  ],
  "variant": "modern",          // items.py variant for tipo "ce"
  "skip": {"CB1": [16, 26]},    // un-extractable items (figures etc.)
  "patch": {"002": {"36": "..."}}  // hand-reconstructed enunciados;
           // a dict {"enunciado": ..., "alternativas": [...]} also replaces alternatives
}

prova/gabarito are local filenames inside the workdir; `arquivo` is the CDN
nomeArquivo used to build the record's `fonte` URL.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from crawler.models import QuestaoExtraida, ProvaMeta, to_questao  # noqa: E402
from crawler.cebraspe import items as items_mod  # noqa: E402
from crawler.cebraspe import mc as mc_mod  # noqa: E402
from crawler.cebraspe.gabarito import parse_gabarito  # noqa: E402
from crawler.shards import SHARD_DIR, load_shard_records, write_shard  # noqa: E402

CDN = "https://cdn.cebraspe.org.br/concursos/{evento}/arquivos/{nome}"


def clean(s):
    s = re.sub(r"[-]", "", s)          # private-use glyphs
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s\d{1,2}$", "", s)      # stray page/line numbers
    return re.sub(r"\s+", " ", s).strip()


def _assunto_for(prova, item, numero):
    if item.get("assunto"):
        return re.sub(r"(?i)^BLOCO\b", "Bloco", item["assunto"])
    for lo, hi, label in prova.get("blocos", []):
        if lo <= numero <= hi:
            return label
    return prova.get("assunto", "")


def parse_items(pdf_path, tipo, variant="modern", audit=False):
    if tipo == "mc":
        return mc_mod.parse_prova(str(pdf_path), audit=audit)
    res = items_mod.parse_prova(str(pdf_path), variant=variant, audit=audit)
    if audit:
        its, dropped = res
        return {n: {"enunciado": t, "alternativas": ["Certo", "Errado"],
                    "assunto": ""} for n, t in its.items()}, dropped
    return {n: {"enunciado": t, "alternativas": ["Certo", "Errado"],
                "assunto": ""} for n, t in res.items()}


def build_records(job, workdir):
    """Yield (cargo_id, records, missing) per cargo; does not touch the dataset."""
    skip = {k: set(v) for k, v in job.get("skip", {}).items()}
    patch = job.get("patch", {})
    variant = job.get("variant", "modern")
    metas = job["meta"]
    cache = {}

    def get_items(prova):
        key = prova["key"]
        if key not in cache:
            cache[key] = parse_items(workdir / prova["prova"],
                                     prova.get("tipo", "ce"), variant)
        return cache[key]

    for c in job["cargos"]:
        recs, missing = [], []
        base_meta = ProvaMeta(
            banca=metas.get("banca", "Cebraspe"), orgao=metas["orgao"],
            cargo=c["cargo"], ano=metas["ano"], fonte="",
            id_orgao=metas["id_orgao"], id_cargo=c["id_cargo"])
        for prova in c["provas"]:
            gab = parse_gabarito(str(workdir / prova["gabarito"]))
            its = get_items(prova)
            meta = base_meta.model_copy(update={
                "fonte": CDN.format(evento=job["evento"],
                                    nome=prova["arquivo"])})
            for n in sorted(gab):
                if gab[n] == "X" or n in skip.get(prova["key"], set()):
                    continue
                p = patch.get(prova["key"], {}).get(str(n))
                if n not in its:
                    if not p:
                        missing.append((prova["key"], n))
                        continue
                    it = {"enunciado": "", "assunto": "",
                          "alternativas": (["Certo", "Errado"]
                                           if prova.get("tipo", "ce") == "ce"
                                           else [])}
                else:
                    it = its[n]
                if isinstance(p, dict):
                    enun = p.get("enunciado", it["enunciado"])
                    alts = p.get("alternativas", it["alternativas"])
                else:
                    enun = p if p else it["enunciado"]
                    alts = it["alternativas"]
                m2 = meta.model_copy(update={
                    "assunto": _assunto_for(prova, it, n)})
                q = QuestaoExtraida(
                    numero=n + prova.get("num_offset", 0),
                    enunciado=clean(enun),
                    alternativas=[clean(a) for a in alts])
                if prova.get("tipo", "ce") == "ce":
                    gab_val = {"C": "certo", "E": "errado"}.get(
                        gab[n], gab[n].lower())
                else:
                    gab_val = gab[n].lower()
                recs.append(to_questao(q, m2, gabarito=gab_val).model_dump())
        yield c["id_cargo"], recs, missing


def assemble(job_path, write=False):
    job = json.loads(Path(job_path).read_text())
    workdir = Path(job_path).resolve().parent
    evento = job["evento"]
    shard_path = SHARD_DIR / f"{evento}.json"
    data = load_shard_records(shard_path) if shard_path.exists() else []
    existing = {q["id"] for q in data}
    total_new = 0
    for idc, recs, missing in build_records(job, workdir):
        dups = [r["id"] for r in recs if r["id"] in existing]
        new = [r for r in recs if r["id"] not in existing]
        seen = set()
        collided = [r["id"] for r in new if r["id"] in seen or seen.add(r["id"])]
        status = f"{idc}: {len(recs)} records"
        if dups:
            status += f" DUP({len(dups)}: {dups[:3]})"
        if collided:
            status += f" !! ID COLLISION {collided[:3]} — set num_offset on the overlapping prova"
        if missing:
            status += f" MISSING {missing}"
        print(status)
        if write:
            data.extend(new)
            existing.update(r["id"] for r in new)
        total_new += len(new)
    print(f"new: {total_new}  evento {evento}: {len(data)} itens"
          + ("" if write else "  (dry-run)"))
    if write and total_new:
        write_shard(evento, data)
    return total_new
