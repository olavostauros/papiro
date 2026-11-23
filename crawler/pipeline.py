"""Motor agnóstico de banca: audit + assemble dirigidos por ``job.json``.

A job (``crawler/jobs/<EVENTO>.json``, também copiado ao workdir) descreve
como prova/gabarito mapeiam em cargos — ver o schema em
``crawler/bancas/base.py``. O adapter é resolvido por ``job["banca"]``
(default ``"cebraspe"``, valor de todos os jobs já comitados).

``prova``/``gabarito`` são nomes locais dentro do workdir; ``arquivo`` é o
nome na fonte, combinado com ``job["evento"]`` via ``adapter.fonte_url``
para montar o ``fonte`` dos registros.
"""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

from . import bancas
from .gabarito import resumo as gab_resumo
from .models import ProvaMeta, QuestaoExtraida, to_questao
from .shards import SHARD_DIR, load_shard_records, write_shard

_TIPO_GAB = {"ce": "certo_errado", "mc": "multipla_escolha"}


def adapter_do(job: dict):
    return bancas.get_adapter(job.get("banca") or "cebraspe")


def clean(s):
    s = re.sub(r"[-]", "", s)  # private-use glyphs
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


def _entradas(workdir: Path, job: dict | None) -> list[dict]:
    """Provas a auditar: as do job (cargos + unmatched) ou todo *.pdf."""
    if job is not None:
        seen = {}
        for c in job["cargos"]:
            for p in c["provas"]:
                seen[p["key"]] = p
        for p in job.get("unmatched", []):
            seen[p["key"]] = p
        return list(seen.values())
    return [{"key": f.stem, "prova": f.name, "gabarito": "", "tipo": "ce"}
            for f in sorted(workdir.glob("*.pdf"))]


def audit(workdir: Path, tipo_override: str | None = None, log=print) -> None:
    """Parseia cada prova do workdir e escreve ``dropped_<key>.txt``."""
    workdir = Path(workdir)
    job_path = workdir / "job.json"
    job = json.loads(job_path.read_text()) if job_path.exists() else None
    adapter = adapter_do(job or {})
    variant = (job or {}).get("variant", "modern")
    for p in _entradas(workdir, job):
        pdf = workdir / p["prova"]
        if not pdf.exists():
            continue
        gab = None
        if p.get("gabarito") and (workdir / p["gabarito"]).exists():
            try:
                gab = adapter.parse_gabarito(workdir / p["gabarito"])
                log(f"== {p['key']}  gabarito: {gab_resumo(gab)}")
            except Exception as ex:
                log(f"== {p['key']}  gabarito FALHOU: {ex}")
        tipo = tipo_override or p.get("tipo", "ce")
        try:
            its, dropped = adapter.parse_prova(pdf, tipo=tipo, variant=variant,
                                               audit=True)
        except Exception as ex:
            log(f"   {p['key']}: PARSE FAIL {ex}")
            continue
        alts = sum(len(v["alternativas"]) for v in its.values())
        log(f"   {p['key']} [{tipo}]: {len(its)} items, {alts} alternativas, "
            f"{len(dropped)} dropped lines -> dropped_{p['key']}.txt")
        (workdir / f"dropped_{p['key']}.txt").write_text(
            "\n".join(f"p{pg} c{c} {t}" for pg, c, t in dropped))
        if gab is not None:
            missing = [n for n in gab.itens
                       if n not in gab.anulados and n not in its]
            if missing:
                log(f"   ! gabarito items not parsed: {missing}")


def build_records(job, workdir, adapter=None):
    """Yield (cargo_id, records, missing) per cargo; does not touch the dataset."""
    adapter = adapter or adapter_do(job)
    skip = {k: set(v) for k, v in job.get("skip", {}).items()}
    patch = job.get("patch", {})
    variant = job.get("variant", "modern")
    metas = job["meta"]
    cache = {}

    def get_items(prova):
        key = prova["key"]
        if key not in cache:
            cache[key] = adapter.parse_prova(workdir / prova["prova"],
                                             tipo=prova.get("tipo", "ce"),
                                             variant=variant)
        return cache[key]

    for c in job["cargos"]:
        recs, missing = [], []
        base_meta = ProvaMeta(
            banca=metas.get("banca", "Cebraspe"), orgao=metas["orgao"],
            cargo=c["cargo"], ano=metas["ano"], fonte="",
            id_orgao=metas["id_orgao"], id_cargo=c["id_cargo"])
        for prova in c["provas"]:
            tipo_gab = _TIPO_GAB.get(prova.get("tipo", "ce"), "certo_errado")
            gab = adapter.parse_gabarito(workdir / prova["gabarito"])
            its = get_items(prova)
            meta = base_meta.model_copy(update={
                "fonte": adapter.fonte_url(job["evento"], prova["arquivo"])})
            for n in gab.itens:
                if n in gab.anulados or n in skip.get(prova["key"], set()):
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
                # letra estranha (ex.: "A" em prova c/e) passa crua: to_questao reprova
                gab_val = (gab.para_dataset(n, tipo_gab)
                           or gab.respostas[n].lower())
                recs.append(to_questao(q, m2, gabarito=gab_val).model_dump())
        yield c["id_cargo"], recs, missing


def assemble(job_path, write=False):
    job = json.loads(Path(job_path).read_text())
    workdir = Path(job_path).resolve().parent
    adapter = adapter_do(job)
    evento = job["evento"]
    shard_path = (SHARD_DIR / f"{evento}.json").resolve()
    if not shard_path.is_relative_to(SHARD_DIR.resolve()):
        raise ValueError(f"evento fora do diretório de shards: {evento!r}")
    data = load_shard_records(shard_path) if shard_path.exists() else []
    existing = {q["id"] for q in data}
    total_new = 0
    new_records = []
    for idc, recs, missing in build_records(job, workdir, adapter):
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
            new_records.extend(new)
            existing.update(r["id"] for r in new)
        total_new += len(new)
    print(f"new: {total_new}  evento {evento}: {len(data)} itens"
          + ("" if write else "  (dry-run)"))
    if write and total_new:
        write_shard(evento, data)
        _db_sync(new_records)
    return total_new


def _db_sync(records):
    """Upsert dos itens novos no banco — só quando DATABASE_URL está definida."""
    if not os.environ.get("DATABASE_URL"):
        return
    try:
        from .db import get_engine, sync_records
        st = sync_records(records, get_engine())
        print(f"db: +{st.inserted} inseridos ({st.skipped} já existiam)")
    except Exception as exc:
        print(f"!! shard gravado, mas db sync falhou: {exc}", file=sys.stderr)
