"""One-shot merge of crawler-leandro's monolith records into data/questions/ shards.

Reads ``crawler/.cache/leandro_questions.json`` (56k flat records extracted
from ``origin/crawler-leandro:web/src/data/questions.json``) and merges into
the sharded dataset, per the decisions in
``.agents/docs/merge-crawler-leandro.md``:

- same id, same fonte             -> field-level merge: olavo is canonical for
                                    enunciado/alternativas/gabarito (coordinate
                                    parser), except KNOWN_BROKEN_OLAVO ids;
                                    leandro fills empty assunto
- same id, different fonte        -> a different prova sharing the slug (TRT8
                                    reaplicacao): append with renamed id
- same (fonte,enunciado)+cargo    -> dupe: skip (fill empty assunto)
- same (fonte,enunciado), other   -> leandro taxonomy (per-vaga decision):
  cargo                             append leandro's record carrying olavo's
                                    canonical content; drop olavo records in
                                    DROP_CARGOS when leandro covers the item
- no match                        -> append; orgao/cargo normalized to the
                                    shard's vocabulary when unambiguous

Usage:

    .venv/bin/python -m crawler.merge_leandro report   # classify + review file
    .venv/bin/python -m crawler.merge_leandro apply    # rewrite touched shards
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from crawler.shards import SHARD_DIR, evento_key, load_shard_records, write_shard

LEANDRO_CACHE = Path(__file__).resolve().parents[1] / "crawler" / ".cache" / "leandro_questions.json"
REVIEW_FILE = Path(__file__).resolve().parents[1] / "crawler" / ".cache" / "merge_review.txt"

FIELDS = ["banca", "orgao", "cargo", "ano", "assunto", "tipo",
          "enunciado", "alternativas", "gabarito", "fonte"]

# Ids whose OLAVO enunciado is known-broken (plan analysis) -> take leandro's.
KNOWN_BROKEN_OLAVO = {
    "cebraspe-2024-anm-analista-direito-029",
    *{f"cebraspe-2024-trf6-analista-contabilidade-{n:03d}" for n in range(23, 30)},
}
KNOWN_BROKEN_OLAVO_RE = re.compile(r"cebraspe-2025-tcemg-.*-019$")

# Ids whose LEANDRO record is known-broken -> never take his content fields;
# flagged on the review list when appended (no olavo counterpart to prefer).
KNOWN_BROKEN_LEANDRO = {
    "cebraspe-2022-trt8-analista-administrativa-044",
    "cebraspe-2026-cbmma-praca-combatente-012",
    "cebraspe-2026-cbmma-praca-combatente-030",
    "cebraspe-2024-pcdf-odontologo-110",
    "cebraspe-2025-tjro-remocao-094",
}

# Eventos where olavo cargos are SUPERSEDED by leandro's taxonomy (per-vaga
# decision): drop the olavo record when leandro covers the same
# (fonte,enunciado) item and does NOT also cover it under the same
# normalized cargo — protects same-named cargos from CB-prova fan-out.
# "*" drops every olavo cargo label in the shard when superseded.
SWAP_ALL = {
    "PM_MA_26", "POLC_AL_22", "TCE_RN_25", "TCE_MG_25", "TCE_RS_25",
    "CNJ_24", "CPNUJE_24", "TRT10_24", "TJ_PA_25_SERVIDOR", "TCE_AC_24",
    "ANM_24", "ARSAL_26", "AGER_MT_23", "TC_DF_23", "TC_DF_24_AUDITOR",
    "BANCO_DO_NORDESTE_22", "PM_RO_22", "PM_SC_23_SOLDADO", "CBM_RO_22",
    "CBM_PA_23_CFP", "TCE_RJ_22_PROCURADOR", "TCE_MS_25_CONSELHEIRO",
}
DROP_CARGOS: dict[str, set[str]] = {
    "CBM_MA_26": {"Praça Especialista Músico Bombeiro Militar"},
    **{ev: {"*"} for ev in SWAP_ALL},
}

# Eventos where leandro's divergent-cargo records are DUPES, not swaps —
# olavo's labels are strictly better (leandro's lose cargo context, e.g.
# bare "Provimento" or specialty without the cargo title). New appends get
# their cargo remapped to the dominant olavo counterpart.
KEEP_OLAVO_CARGO: set[str] = {
    "TJ_MT_25_NOTARIOS", "TJ_RR_25", "TJ_PE_24_NOTARIOS", "BANRISUL_25",
}

# Explicit leandro -> olavo cargo remaps for keep-olavo eventos (covers
# gap-fill appends whose cargo never co-occurs in a matched item).
CARGO_REMAP: dict[str, dict[str, str]] = {
    "TJ_MT_25_NOTARIOS": {
        "Provimento": "Notário — Outorga por Provimento",
        "Remoção": "Notário — Outorga por Remoção",
    },
    "TJ_RR_25": {
        "Provimento": "Notários – Outorga por Provimento",
        "Remoção": "Notários – Outorga por Remoção",
    },
    "TJ_PE_24_NOTARIOS": {
        "Provimento": "Escrevente/Notário — Provimento",
        "Remoção": "Escrevente/Notário — Remoção",
    },
    "BANRISUL_25": {
        "Administração de Banco de Dados":
            "Técnico em Tecnologia da Informação II – Administração de Banco de Dados",
        "Desenvolvimento de Software":
            "Técnico em Tecnologia da Informação II – Desenvolvimento de Software",
        "Tecnologia: Segurança, Infra e Operação":
            "Técnico em Tecnologia da Informação II – Segurança, Infra e Operação",
        "Transformação Digital e Gestão de Ti":
            "Técnico em Tecnologia da Informação II – Transformação Digital e Gestão de TI",
    },
}

# Tokens ignored when judging whether a leandro cargo "renames" an olavo
# cargo (leftover relabel): generic structural words of the edital style.
STOP_TOKENS = {
    "de", "da", "do", "das", "dos", "e", "ou", "a", "o", "em", "com", "para",
    "cargo", "area", "perfil", "especialidade", "orientacao", "enfase",
    "foco", "atuacao", "sem", "in", "n", "eou",
}


def tokens(label: str) -> set[str]:
    toks = set(re.findall(r"[a-z0-9]+", unicodedata.normalize(
        "NFKD", label).encode("ascii", "ignore").decode().lower()))
    return toks - STOP_TOKENS


def _tok_eq(a: str, b: str) -> bool:
    """Fuzzy token equality: identical or common prefix >= 6 chars — catches
    inflection variants (economia/economicas, agronomia/agronomica)."""
    if a == b:
        return True
    n = min(len(a), len(b))
    return n >= 6 and a[:6] == b[:6]


def _covered(ot: set[str], lt: set[str]) -> int | None:
    """If every olavo token has a fuzzy match in lt, return how many leandro
    tokens remain uncovered (the "distance"); else None."""
    if not all(any(_tok_eq(t, u) for u in lt) for t in ot):
        return None
    return sum(1 for u in lt if not any(_tok_eq(t, u) for t in ot))


def rename_target(ocargo: str, partners: Counter) -> str | None:
    """Leandro cargo that renames `ocargo`: contains all its tokens (fuzzy)
    and adds the fewest — only when the minimum is unique (a 1:N split like
    an umbrella -> vagas has many equal-distance candidates and is skipped)."""
    ot = tokens(ocargo)
    cands = []
    for lcargo in partners:
        if norm(lcargo) == norm(ocargo):
            continue  # same logical cargo — keep the shard's label
        extra = _covered(ot, tokens(lcargo))
        if extra is not None:
            cands.append((extra, lcargo))
    if not cands:
        return None
    cands.sort()
    if len(cands) > 1 and cands[0][0] == cands[1][0]:
        return None
    return cands[0][1]


def dominant_target(ocargo: str, partners: Counter,
                    rev: dict[str, Counter]) -> str | None:
    """Fallback rename target via pairing strength: the leandro cargo that
    co-occurs with `ocargo`'s items most often, by >=2x over the runner-up,
    provided the relation is mutual (its dominant olavo partner is ocargo).
    Used when token containment fails on word variants (economia/economicas).
    A 1:N split yields no dominant partner -> skipped."""
    ps = sorted(((c, l) for l, c in partners.items() if norm(l) != norm(ocargo)),
                reverse=True)
    if not ps:
        return None
    top_c, top_l = ps[0]
    if top_c < 10 or (len(ps) > 1 and ps[1][0] * 2 > top_c):
        return None
    back = rev.get(top_l)
    if back and back.most_common(1)[0][0] != ocargo:
        return None
    return top_l

GENERIC_ASSUNTOS = {"conhecimentos gerais", "conhecimentos especificos",
                    "conhecimentos basicos", "conhecimentos específicos"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def olavo_broken(rid: str) -> bool:
    return rid in KNOWN_BROKEN_OLAVO or bool(KNOWN_BROKEN_OLAVO_RE.match(rid))


def reaplicacao_id(rid: str, fonte: str) -> str:
    """Insert -reaplicacao before the trailing -NNN when the prova is one."""
    if "REAPLICACAO" not in fonte.upper():
        return rid
    return re.sub(r"-(\d+)$", r"-reaplicacao-\1", rid)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    shards = {p.stem: load_shard_records(p) for p in sorted(SHARD_DIR.glob("*.json"))}
    leandro = json.loads(LEANDRO_CACHE.read_text())

    olavo_by_id = {r["id"]: (ev, r) for ev, rs in shards.items() for r in rs}
    # (fonte, norm enunciado) -> [(evento, record)]
    ofe: dict[tuple[str, str], list[tuple[str, dict]]] = defaultdict(list)
    for ev, rs in shards.items():
        for r in rs:
            ofe[(r["fonte"], norm(r["enunciado"]))].append((ev, r))
    # (fonte, norm enunciado) -> set of leandro's normalized cargos on the item
    lfe: dict[tuple[str, str], set[str]] = defaultdict(set)
    for lr in leandro:
        lfe[(lr["fonte"], norm(lr["enunciado"]))].add(norm(lr["cargo"]))
    # leandro cargo -> dominant olavo cargo, for keep-olavo cargo remaps
    rev_pairs: dict[str, dict[str, Counter]] = defaultdict(
        lambda: defaultdict(Counter))
    for lr in leandro:
        for ev_m, m in ofe.get((lr["fonte"], norm(lr["enunciado"])), []):
            rev_pairs[ev_m][lr["cargo"]][m["cargo"]] += 1
    rev_map = {ev: {lc: c.most_common(1)[0][0] for lc, c in cs.items()}
               for ev, cs in rev_pairs.items()}
    # shard cargo vocabulary: normalized -> display label
    shard_cargos = {ev: {norm(r["cargo"]): r["cargo"] for r in rs}
                    for ev, rs in shards.items()}

    stats = Counter()
    review: list[str] = []
    appends: dict[str, list[dict]] = defaultdict(list)
    drops: dict[str, set[str]] = defaultdict(set)  # olavo ids to drop per evento
    pairs: dict[str, Counter] = defaultdict(Counter)  # cargo correspondence
    seen_ids: set[str] = set()

    for lr in leandro:
        ev = evento_key(lr["fonte"], lr)
        stats[f"{ev}::total"] += 1
        if "cebraspe.org.br" not in lr["fonte"]:
            stats["skip::non_cebraspe"] += 1
            review.append(f"non-cebraspe fonte skipped: {lr['id']} <- {lr['fonte']}")
            continue

        o_hit = olavo_by_id.get(lr["id"])
        key = (lr["fonte"], norm(lr["enunciado"]))
        matches = ofe.get(key, [])
        same_cargo = [m for m in matches if norm(m[1]["cargo"]) == norm(lr["cargo"])]

        if o_hit is not None:
            ev_o, o = o_hit
            if o["fonte"] != lr["fonte"]:
                # Different prova sharing the slug (TRT8 reaplicacao).
                lr = dict(lr, id=reaplicacao_id(lr["id"], lr["fonte"]))
                if lr["id"] in seen_ids or lr["id"] in olavo_by_id:
                    stats[f"{ev}::skip_reaplicacao_id_taken"] += 1
                    continue
                appends[ev].append(lr)
                seen_ids.add(lr["id"])
                stats[f"{ev}::append_reaplicacao"] += 1
                continue
            if all(lr[f] == o[f] for f in FIELDS):
                stats[f"{ev}::identical"] += 1
                continue
            # Field-level merge into the olavo record (in place).
            if olavo_broken(lr["id"]):
                for f in ("enunciado", "alternativas", "gabarito"):
                    o[f] = lr[f]
                review.append(f"olavo-broken fixed from leandro: {lr['id']}")
            else:
                for f in ("enunciado", "alternativas", "gabarito"):
                    if norm(str(lr.get(f) or "")) != norm(str(o.get(f) or "")):
                        review.append(f"content diff (kept olavo): {lr['id']} field={f}")
            if not o["assunto"] and lr["assunto"]:
                o["assunto"] = lr["assunto"]
            stats[f"{ev}::merged_collision"] += 1
            continue

        if matches:
            pairs[ev].update((m[1]["cargo"], lr["cargo"]) for m in matches)
            if same_cargo:
                m = same_cargo[0][1]
                if not m["assunto"] and lr["assunto"]:
                    m["assunto"] = lr["assunto"]
                stats[f"{ev}::dupe_same_cargo"] += 1
                continue
            if ev in KEEP_OLAVO_CARGO:
                stats[f"{ev}::dupe_keep_olavo_cargo"] += 1
                continue
            # Leandro covers the item under a cargo olavo lacks: append with
            # olavo's canonical content fields + leandro's identity.
            base = next((m[1] for m in matches if not olavo_broken(m[1]["id"])),
                        matches[0][1])
            rec = dict(lr)
            if not olavo_broken(base["id"]):
                for f in ("enunciado", "alternativas", "gabarito", "assunto", "orgao", "tipo"):
                    rec[f] = base[f]
            else:
                review.append(f"olavo-broken base kept leandro content: {lr['id']}")
            rec["cargo"] = shard_cargos.get(ev, {}).get(norm(rec["cargo"]), rec["cargo"])
            appends[ev].append(rec)
            seen_ids.add(rec["id"])
            stats[f"{ev}::append_coverage"] += 1
            # Mark superseded olavo cargos for drop — only when leandro does
            # not also cover the item under that same cargo (fan-out guard).
            drop_set = DROP_CARGOS.get(ev, set())
            for ev_m, m in matches:
                if (ev_m == ev and ("*" in drop_set or m["cargo"] in drop_set)
                        and norm(m["cargo"]) not in lfe[key]):
                    drops[ev].add(m["id"])
            continue

        # No match at all: genuinely new item/prova.
        rec = dict(lr)
        remap = CARGO_REMAP.get(ev, {})
        if rec["cargo"] in remap:
            rec["cargo"] = remap[rec["cargo"]]
        elif ev in KEEP_OLAVO_CARGO and rec["cargo"] in rev_map.get(ev, {}):
            rec["cargo"] = rev_map[ev][rec["cargo"]]
        if ev in shards:
            orecs = shards[ev]
            orgaos = {r["orgao"] for r in orecs}
            cargos = {norm(r["cargo"]): r["cargo"] for r in orecs}
            if len(orgaos) == 1:
                rec["orgao"] = next(iter(orgaos))
            elif norm(rec["orgao"]) in {norm(o) for o in orgaos}:
                rec["orgao"] = next(o for o in orgaos if norm(o) == norm(rec["orgao"]))
            else:
                review.append(f"orgao novo no shard {ev}: {rec['orgao']!r} vs {sorted(orgaos)}")
            if norm(rec["cargo"]) in cargos:
                rec["cargo"] = cargos[norm(rec["cargo"])]
        if rec["id"] in KNOWN_BROKEN_LEANDRO:
            review.append(f"leandro-broken appended, conferir PDF: {rec['id']}")
        appends[ev].append(rec)
        seen_ids.add(rec["id"])
        stats[f"{ev}::append_new"] += 1

    # ---- report ----
    print(f"{'evento':28s} {'ident':>6s} {'merge':>6s} {'dupe':>6s} {'cov+':>5s} {'new+':>5s} {'reap':>4s} {'drop':>5s}")
    for ev in sorted({k.split('::')[0] for k in stats if '::' in k}):
        print(f"{ev:28s} {stats[f'{ev}::identical']:6d} {stats[f'{ev}::merged_collision']:6d} "
              f"{stats[f'{ev}::dupe_same_cargo'] + stats[f'{ev}::dupe_keep_olavo_cargo']:6d} "
              f"{stats[f'{ev}::append_coverage']:5d} {stats[f'{ev}::append_new']:5d} "
              f"{stats[f'{ev}::append_reaplicacao']:4d} {len(drops[ev]):5d}")
    print(f"\nappends: {sum(len(v) for v in appends.values())}  drops: {sum(len(v) for v in drops.values())}  "
          f"skipped non-cebraspe: {stats['skip::non_cebraspe']}")

    print(f"review file: {REVIEW_FILE}")

    if mode != "apply":
        _write_review(pairs, review)
        return

    # ---- apply ----
    # olavo cargo -> Counter of leandro partners (rename/relabel resolution)
    fwd_map: dict[str, dict[str, Counter]] = defaultdict(
        lambda: defaultdict(Counter))
    for ev, pc in pairs.items():
        for (o, l), c in pc.items():
            fwd_map[ev][o][l] += c

    for ev, recs in appends.items():
        existing = shards.get(ev, [])
        drop_ids = drops.get(ev, set())
        drop_set = DROP_CARGOS.get(ev, set())
        kept = [r for r in existing if r["id"] not in drop_ids]
        # Relabel survivors of a superseded cargo to its leandro rename —
        # keeps one label per logical cargo (id slug keeps the old cargo).
        for r in kept:
            if "*" in drop_set or r["cargo"] in drop_set:
                partners = fwd_map.get(ev, {}).get(r["cargo"], Counter())
                tgt = (rename_target(r["cargo"], partners)
                       or dominant_target(r["cargo"], partners,
                                          rev_pairs.get(ev, {})))
                if tgt:
                    review.append(f"relabel {ev}: {r['cargo']!r} -> {tgt!r} ({r['id']})")
                    r["cargo"] = tgt
        ids = {r["id"] for r in kept}
        assert not ids & {r["id"] for r in recs}, f"{ev}: append id collision"
        write_shard(ev, kept + recs)
        print(f"{ev}: {len(existing)} -> {len(kept)+len(recs)} (+{len(recs)} -{len(drop_ids)})")
    _write_review(pairs, review)


def _write_review(pairs: dict, review: list[str]) -> None:
    with REVIEW_FILE.open("w") as f:
        f.write("# merge_leandro review\n\n")
        f.write("## cargo correspondence (olavo -> leandro)\n")
        for ev in sorted(pairs):
            f.write(f"\n### {ev}\n")
            for (a, b), c in pairs[ev].most_common():
                f.write(f"  {c:5d}  {a!r} -> {b!r}\n")
        f.write("\n## flagged records\n")
        f.writelines(f"  {l}\n" for l in review)


if __name__ == "__main__":
    main()
