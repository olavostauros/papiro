"""Backfill de textos-base nos shards existentes.

Re-baixa cada prova pelo ``fonte`` do shard, roda o parser da banca (que
agora coleta blocos ``Texto <ref>``) e relinka os itens: o conteúdo vai para
o array internado ``textos`` do shard e o item ganha ``"texto": <idx>``.
Números de item casam pelo sufixo ``-NNN`` do id, descontado o
``num_offset`` do job quando o ``crawler/jobs/<EVENTO>.json`` existe.

    .venv/bin/python -m crawler textos                 # dry-run, relatório
    .venv/bin/python -m crawler textos --write         # aplica
    .venv/bin/python -m crawler textos AGEPAR_PR_26 --write

Variant: usa ``job["variant"]`` quando há job; senão tenta ``modern`` e cai
para ``old`` se o parse veio quase vazio. Depois do ``--write``, rode
``python -m crawler.db sync`` — rows existentes ganham ``texto_id``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

from . import bancas
from .shards import SHARD_DIR

JOBS_DIR = Path(__file__).resolve().parent / "jobs"
CACHE_DIR = Path("/tmp/papiro_textos")

_BANCA_ADAPTER = {"cebraspe": "cebraspe", "fcc": "fcc", "fgv": "fgv"}
_ENUN_REF_RE = re.compile(r"textos?\s+([A-Z]{1,5}\d[A-Z]?\d*)", re.I)
_TIPO_ITEM = {"multipla_escolha": "mc", "certo_errado": "ce"}


def _adapter(shard: dict):
    name = _BANCA_ADAPTER.get((shard.get("banca") or "").lower())
    return bancas.get_adapter(name) if name else None


def _download(fonte: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{hashlib.sha1(fonte.encode()).hexdigest()}.pdf"
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(fonte, headers={"User-Agent": "papiro/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        import threading
        tmp = dest.with_suffix(f".part{threading.get_ident()}")
        tmp.write_bytes(data)
        tmp.replace(dest)  # rename atômico — sem leitura de PDF parcial
    return dest


def _job_map(evento: str, shard: dict) -> dict:
    """fonte → {tipo, variant, num_offset} a partir do job.json, se existir."""
    job_path = JOBS_DIR / f"{evento}.json"
    if not job_path.exists():
        return {}
    job = json.loads(job_path.read_text())
    variant = job.get("variant", "modern")
    try:
        adapter = bancas.get_adapter(job.get("banca") or "cebraspe")
    except ValueError:
        return {}
    out = {}
    for c in job.get("cargos", []):
        for p in c.get("provas", []):
            out[adapter.fonte_url(evento, p["arquivo"])] = {
                "tipo": p.get("tipo", "ce"), "variant": variant,
                "num_offset": p.get("num_offset", 0)}
    return out


def _parse(pdf: Path, adapter, tipo: str, variant: str):
    try:
        return adapter.parse_prova(pdf, tipo=tipo, variant=variant)
    except Exception:
        return {}


def _textos_por_num(parsed: dict) -> dict[int, dict]:
    return {n: it["texto"] for n, it in parsed.items() if it.get("texto")}


def backfill_shard(path: Path, write: bool, cache_dir: Path, log=print) -> dict:
    shard = json.loads(path.read_text())
    evento = shard.get("evento", path.stem)
    adapter = _adapter(shard)
    stats = {"evento": evento, "provas": 0, "links": 0, "refs_sem_texto": 0,
             "skipped": adapter is None}
    if adapter is None:
        return stats

    job = _job_map(evento, shard)
    textos: list[dict] = shard.setdefault("textos", [])
    intern = {(t.get("ref", ""), t.get("conteudo", "")): i
              for i, t in enumerate(textos)}

    def link(item: dict, texto: dict) -> None:
        key = (texto.get("ref", ""), texto.get("conteudo", ""))
        if key not in intern:
            intern[key] = len(textos)
            textos.append({"ref": texto.get("ref", ""),
                           "conteudo": texto.get("conteudo", ""),
                           "citacao": texto.get("citacao", ""),
                           "imagem": bool(texto.get("imagem"))})
        item["texto"] = intern[key]

    for pidx, prova in enumerate(shard["provas"]):
        fonte = prova["fonte"]
        its = [it for it in shard["itens"] if it["prova"] == pidx]
        if not its:
            continue
        stats["provas"] += 1
        meta = job.get(fonte, {})
        tipo = meta.get("tipo") or _TIPO_ITEM.get(its[0]["tipo"], "ce")
        variant = meta.get("variant", "modern")
        offset = meta.get("num_offset", 0)
        try:
            pdf = _download(fonte, cache_dir)
        except Exception as exc:
            log(f"  !! download falhou {fonte}: {exc}")
            continue
        parsed = _parse(pdf, adapter, tipo, variant)
        if tipo == "ce" and variant == "modern" \
                and len(parsed) < len(its) * 0.5:
            alt = _parse(pdf, adapter, tipo, "old")
            if len(alt) > len(parsed):
                parsed, variant = alt, "old"
        por_num = _textos_por_num(parsed)
        por_ref = {t["ref"]: t for t in por_num.values() if t.get("ref")}
        for it in its:
            if "texto" in it:
                continue  # já linkado — idempotente
            t = None
            try:
                n = int(it["id"].rsplit("-", 1)[1]) - offset
                t = por_num.get(n)
            except (ValueError, IndexError):
                pass
            if t is None:
                m = _ENUN_REF_RE.search(it["enunciado"])
                if m:
                    t = por_ref.get(m.group(1).upper())
                    if t is None:
                        stats["refs_sem_texto"] += 1
            if t is not None:
                link(it, t)
                stats["links"] += 1
    if not stats["links"] and not any("texto" in it for it in shard["itens"]):
        shard.pop("textos", None)
    if write and stats["links"]:
        path.write_text(json.dumps(shard, ensure_ascii=False, indent=1) + "\n")
    return stats


def main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m crawler textos")
    ap.add_argument("eventos", nargs="*", help="stems de shard (default: todos)")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--workers", type=int, default=1,
                    help="shards em paralelo (default 1; download+parse são I/O)")
    ap.add_argument("--shard-dir", default=str(SHARD_DIR))
    ap.add_argument("--cache-dir", default=str(CACHE_DIR))
    args = ap.parse_args(argv)

    shard_dir = Path(args.shard_dir)
    cache_dir = Path(args.cache_dir)
    paths = ([shard_dir / f"{e}.json" for e in args.eventos]
             if args.eventos else sorted(shard_dir.glob("*.json")))
    paths = [p for p in paths if p.exists()]
    total_links = total_refs = done = 0

    def report(st):
        flag = "" if args.write else "  (dry-run)"
        skip = "  [adapter ausente]" if st["skipped"] else ""
        print(f"{st['evento']}: {st['links']} links "
              f"({st['refs_sem_texto']} refs sem texto, "
              f"{st['provas']} provas){skip}{flag}", flush=True)

    if args.workers > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(backfill_shard, p, args.write, cache_dir,
                              lambda m: print(m, flush=True)): p
                    for p in paths}
            for f in as_completed(futs):
                st = f.result()
                done += 1
                total_links += st["links"]
                total_refs += st["refs_sem_texto"]
                report(st)
    else:
        for p in paths:
            st = backfill_shard(p, args.write, cache_dir)
            done += 1
            total_links += st["links"]
            total_refs += st["refs_sem_texto"]
            report(st)
    print(f"\n{done} shards, {total_links} itens linkados, "
          f"{total_refs} refs sem texto extraído"
          + ("" if args.write else " — dry-run; use --write"))
    return 0
