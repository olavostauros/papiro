"""Sharded dataset layout: data/questions/<EVENTO>.json at the repo root.

The monolithic web/src/data/questions.json was replaced by one file per
evento (Cebraspe concurso id, from the /concursos/<ID>/ path in `fonte`;
`EXTERNO_<banca>_<orgao>_<ano>` for non-Cebraspe sources). Repeated
dimensions (banca/orgao/cargo/assunto/fonte) are interned per shard:
items reference them by index.

Shard schema:

{
  "evento": "PF_24",
  "banca": "Cebraspe",
  "orgaos": ["Polícia Federal"],            # referenced by item.orgao
  "cargos": ["Escrivão de Polícia Federal"],
  "assuntos": ["", "Direito Administrativo"],
  "provas": [{"fonte": "https://cdn.../arquivos/106_PF_015_01.pdf"}],
  "itens": [
    {"id": "cebraspe-2024-pf-escrivao-042",
     "prova": 0, "orgao": 0, "cargo": 0, "ano": 2024, "assunto": 1,
     "tipo": "certo_errado", "enunciado": "...", "gabarito": "certo",
     "alternativas": ["A", "B"]}             # omitted iff ["Certo", "Errado"]
  ]
}

The dataset is served to the site by an API running on the VM (Docker);
`web/` no longer bundles it. `shard_to_records`/`load_shard_records`
flatten a shard back into the original record shape.

One-shot conversion from the old monolith: `.venv/bin/python -m crawler.shards`
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SHARD_DIR = DATA_DIR / "questions"
MONOLITH = DATA_DIR / "questions.json"  # legacy input for the one-shot convert

CERTO_ERRADO = ["Certo", "Errado"]

_CONCURSO_RE = re.compile(r"/concursos/([^/]+)/")
_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return _SAFE_RE.sub("_", ascii_text).strip("_")


def evento_key(fonte: str, record: dict | None = None) -> str:
    """Shard file stem for a `fonte` URL (record needed only for non-Cebraspe)."""
    m = _CONCURSO_RE.search(fonte)
    if m:
        return _slug(m.group(1))
    if record is None:
        return _slug(fonte)
    return f"EXTERNO_{_slug(record['banca'])}_{_slug(record['orgao'])}_{record['ano']}"


def records_to_shard(evento: str, records: list[dict]) -> dict:
    """Intern repeated dimensions of flat Questao records into a shard."""
    bancas = {r["banca"] for r in records}
    if len(bancas) > 1:
        raise ValueError(f"{evento}: bancas mistas {bancas}")
    orgaos: dict[str, int] = {}
    cargos: dict[str, int] = {}
    assuntos: dict[str, int] = {}
    provas: dict[str, int] = {}

    def intern(table: dict[str, int], value: str) -> int:
        if value not in table:
            table[value] = len(table)
        return table[value]

    itens = []
    for r in records:
        item = {
            "id": r["id"],
            "prova": intern(provas, r["fonte"]),
            "orgao": intern(orgaos, r["orgao"]),
            "cargo": intern(cargos, r["cargo"]),
            "ano": r["ano"],
            "assunto": intern(assuntos, r["assunto"]),
            "tipo": r["tipo"],
            "enunciado": r["enunciado"],
            "gabarito": r["gabarito"],
        }
        if r["alternativas"] != CERTO_ERRADO:
            item["alternativas"] = r["alternativas"]
        itens.append(item)

    return {
        "evento": evento,
        "banca": next(iter(bancas)),
        "orgaos": list(orgaos),
        "cargos": list(cargos),
        "assuntos": list(assuntos),
        "provas": [{"fonte": f} for f in provas],
        "itens": itens,
    }


def shard_to_records(shard: dict) -> list[dict]:
    """Flatten a shard back into the original record shape (order preserved)."""
    fontes = [p["fonte"] for p in shard["provas"]]
    out = []
    for it in shard["itens"]:
        out.append({
            "id": it["id"],
            "banca": shard["banca"],
            "orgao": shard["orgaos"][it["orgao"]],
            "cargo": shard["cargos"][it["cargo"]],
            "ano": it["ano"],
            "assunto": shard["assuntos"][it["assunto"]],
            "tipo": it["tipo"],
            "enunciado": it["enunciado"],
            "alternativas": it.get("alternativas", CERTO_ERRADO),
            "gabarito": it["gabarito"],
            "fonte": fontes[it["prova"]],
        })
    return out


def load_shard_records(path: Path) -> list[dict]:
    return shard_to_records(json.loads(path.read_text()))


def iter_records(dataset: Path):
    """Flat records de um diretório de shards ou de um JSON legado (lista)."""
    dataset = Path(dataset)
    if dataset.is_dir():
        for p in sorted(dataset.glob("*.json")):
            yield from shard_to_records(json.loads(p.read_text(encoding="utf-8")))
    elif dataset.exists():
        yield from json.loads(dataset.read_text(encoding="utf-8"))


def write_shard(evento: str, records: list[dict], shard_dir: Path = SHARD_DIR) -> Path:
    shard_dir = Path(shard_dir)
    shard_dir.mkdir(parents=True, exist_ok=True)
    path = (shard_dir / f"{evento}.json").resolve()
    if not path.is_relative_to(shard_dir.resolve()):
        raise ValueError(f"evento fora do diretório de shards: {evento!r}")
    shard = records_to_shard(evento, records)
    path.write_text(json.dumps(shard, ensure_ascii=False, indent=1) + "\n")
    return path


def convert(shard_dir: Path = SHARD_DIR) -> None:
    data = json.loads(MONOLITH.read_text())
    grouped: dict[str, list[dict]] = {}
    for r in data:
        grouped.setdefault(evento_key(r["fonte"], r), []).append(r)
    total = 0
    for ev, recs in sorted(grouped.items()):
        path = write_shard(ev, recs, shard_dir)
        total += len(recs)
        print(f"{path.name}: {len(recs)} itens, {path.stat().st_size // 1024} KB")
    print(f"{len(grouped)} shards, {total} itens")


if __name__ == "__main__":
    convert()
