"""CLI única do crawler — ``python -m crawler <cmd>``.

Comandos job-driven (next/files/fetch/audit/assemble) resolvem o adapter da
banca (``--banca``, default cebraspe) e não conhecem layout de banca.
``discover``/``ingest``/``db`` delegam ao adapter/ao pipeline manifesto.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from . import bancas
from .pipeline import assemble, audit
from .shards import SHARD_DIR

JOBS_DIR = Path(__file__).resolve().parent / "jobs"


def done_eventos():
    # shard filenames são o identificador do evento (EXTERNO_* incluso)
    done = {p.stem for p in SHARD_DIR.glob("*.json")}
    skip = JOBS_DIR / "_skip.json"        # eventos não-ingeríveis, com motivo
    if skip.exists():
        done |= set(json.loads(skip.read_text()))
    return done


def cmd_next(args):
    adapter = bancas.get_adapter(args.banca)
    done = done_eventos()
    ranquear = getattr(adapter, "ranquear",
                       lambda evs: sorted(evs, key=lambda e: -(e.get("eventoAno") or 0)))
    shown = probed = 0
    for e in ranquear(adapter.list_eventos()):
        if e["eventoURL"] in done:
            continue
        status = ""
        if args.probe:
            try:
                det = adapter.get_evento(e["idEvento"])
                nprov = sum(1 for a in det.get("arquivosGabarito") or []
                            if adapter.arquivo_kind(a) == "prova")
                ngab = sum(1 for a in det.get("arquivosGabarito") or []
                           if adapter.arquivo_kind(a) == "gabarito")
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
    adapter = bancas.get_adapter(args.banca)
    det = adapter.get_evento(args.evento)
    print(det["eventoNomeAbreviado"], "|", det["eventoNomeCompleto"],
          "| ano:", det["eventoAno"], "| vagas:", det["eventoTotalVagas"])
    print("\n== CARGOS ==")
    for c in det.get("eventoCargos") or []:
        print(f'  {c["idArea"]}: {c["area"]}')
    print("\n== ARQUIVOS ==")
    for a in det.get("arquivosGabarito") or []:
        kind = adapter.arquivo_kind(a)
        cargos = ",".join(adapter.arquivo_cargos(a))
        print(f'  [{kind:8}] {a["nomeArquivo"]}  cargos={cargos or "-"}')
        print(f'             {(a.get("descricaoArquivo") or "")[:90]}')


def _anos_do_nome(nome: str) -> set[int]:
    """Anos embutidos no nome do evento — só tokens puramente numéricos
    (`HUB_21` → {2021}, `APEX_22_2` → {2022}, `CD26PL` → vazio)."""
    anos: set[int] = set()
    for tok in re.split(r"[^A-Za-z0-9]+", nome):
        if re.fullmatch(r"\d{2}", tok):
            anos.add(2000 + int(tok))
        elif re.fullmatch(r"(?:19|20)\d{2}", tok):
            anos.add(int(tok))
    return anos


def cmd_fetch(args):
    adapter = bancas.get_adapter(args.banca)
    det = adapter.get_evento(args.evento)
    evento = det["eventoURL"]
    base = Path(os.environ.get("PAPIRO_WORKDIR", "/tmp")).resolve()
    if args.workdir:
        workdir = Path(args.workdir)
    else:
        workdir = (base / evento.lower()).resolve()
        if not workdir.is_relative_to(base):
            raise ValueError(f"evento fora do workdir base: {evento!r}")
    manifest = adapter.fetch(det, workdir)
    job = adapter.draft_job(det, manifest, workdir)
    (workdir / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1))
    print(f"\njob skeleton -> {workdir}/job.json  "
          f"({len(job['cargos'])} cargos, {len(job['unmatched'])} unmatched provas)")
    # a API reporta o ano do EDITAL — para famílias como a HUB o ano do
    # programa é o do nome do evento (caso HUB_21, 2026-11-25). Aviso, não
    # correção: a decisão final fica na curadoria do job.
    try:
        ano_meta = int(job["meta"]["ano"])
    except (KeyError, TypeError, ValueError):
        ano_meta = None
    anos_nome = _anos_do_nome(evento)
    if ano_meta is not None and anos_nome and ano_meta not in anos_nome:
        print(f"\nAVISO: meta.ano={ano_meta} diverge do ano no nome do evento "
              f"({sorted(anos_nome)}) — a API reporta o ano do edital; "
              "confira o ano do programa na curadoria")


def cmd_audit(args):
    audit(Path(args.workdir), tipo_override=args.tipo)


def cmd_assemble(args):
    assemble(Path(args.workdir) / "job.json", write=args.write)


def cmd_discover(args, extra):
    if args.banca != "cebraspe":
        sys.exit(f"discover não implementado para {args.banca}")
    from .bancas.cebraspe import api
    return api.manifest_main(extra)


def cmd_ingest(extra):
    from . import ingest
    return ingest.main(extra)


def cmd_db(extra):
    from . import db
    return db.main(extra)


def cmd_textos(extra):
    from . import textos
    return textos.main(extra)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m crawler")
    ap.add_argument("--banca", default="cebraspe", choices=sorted(bancas.BANCAS),
                    help="adapter da banca (default: cebraspe)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("next", help="rank de eventos não ingeridos")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--probe", type=int, default=0,
                   help="fetch details for up to N candidates")
    p.set_defaults(fn=cmd_next)
    p = sub.add_parser("files", help="cargos + arquivos de um evento")
    p.add_argument("evento")
    p.set_defaults(fn=cmd_files)
    p = sub.add_parser("fetch", help="baixa PDFs e rascunha job.json")
    p.add_argument("evento")
    p.add_argument("--workdir")
    p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("audit", help="parseia provas do workdir")
    p.add_argument("--workdir", required=True)
    p.add_argument("--tipo", choices=["ce", "mc"])
    p.set_defaults(fn=cmd_audit)
    p = sub.add_parser("assemble", help="monta o shard a partir do job")
    p.add_argument("--workdir", required=True)
    p.add_argument("--write", action="store_true")
    p.set_defaults(fn=cmd_assemble)
    for nome, helptext in (("discover", "gera o manifesto da banca"),
                           ("ingest", "pipeline manifesto → dataset"),
                           ("db", "sync/stats do Postgres"),
                           ("textos", "backfill de textos-base nos shards")):
        p = sub.add_parser(nome, help=helptext)
        p.set_defaults(passthrough=True)
    args, extra = ap.parse_known_args(argv)
    if getattr(args, "passthrough", False):
        fn = {"discover": cmd_discover, "ingest": cmd_ingest, "db": cmd_db,
              "textos": cmd_textos}[args.cmd]
        return (fn(extra) if args.cmd != "discover" else fn(args, extra)) or 0
    if extra:
        ap.error(f"unrecognized arguments: {' '.join(extra)}")
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
