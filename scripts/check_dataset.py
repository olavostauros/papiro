#!/usr/bin/env python3
"""Gate de higiene do dataset — CI (`.github/workflows/ci.yml`) e uso local
antes de commitar shards novos.

Falham (exit 1):

- shard que não parseia via ``crawler.shards.load_shard_records``;
- registro sem ``id``, ``enunciado`` ou ``gabarito``;
- ``id`` repetido dentro do mesmo shard;
- padrão de segredo em ``data/`` (SECURITY.md §6 — varrer shards novos);
  o relatório nunca imprime o trecho casado, só o nome do padrão.

Aviso (não falha): ``id`` repetido entre shards distintos — baseline
conhecido HUB_20×HUB_21; reportar ao arquivista para reconciliação.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.shards import load_shard_records  # noqa: E402

# Nomes são reportados; o trecho casado nunca vai para o log (SECURITY.md §1 —
# o incidente de 2026-11-24 foi exatamente um valor de segredo no transcript).
SEGREDOS = {
    "firecrawl api key": r"fc-[A-Za-z0-9]{20,}",
    "api key sk-*": r"sk-[A-Za-z0-9_-]{20,}",
    "github pat": r"(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{22,})",
    "aws access key id": r"AKIA[0-9A-Z]{16}",
    "private key pem": r"-{5}BEGIN [A-Z0-9 ]*PRIVATE KEY-{5}",
    "dsn com senha": (
        r"(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis)"
        r"://[^\s/'\":@]+:[^\s/'\"@]+@"
    ),
}


def main() -> int:
    shard_dir = ROOT / "data" / "questions"
    erros: list[str] = []
    avisos: list[str] = []
    donos: dict[str, str] = {}
    total = 0

    for path in sorted(shard_dir.glob("*.json")):
        try:
            records = load_shard_records(path)
        except Exception as exc:
            erros.append(f"{path.name}: shard inválido — {exc}")
            continue

        locais: set[str] = set()
        for rec in records:
            total += 1
            rid = rec.get("id")
            if not rid:
                erros.append(f"{path.name}: registro sem id")
                continue
            for campo in ("enunciado", "gabarito"):
                if not rec.get(campo):
                    erros.append(f"{path.name}: {rid} sem {campo}")
            if rid in locais:
                erros.append(f"{path.name}: id duplicado no shard — {rid}")
            locais.add(rid)
            outro = donos.setdefault(rid, path.name)
            if outro != path.name:
                avisos.append(f"id em shards distintos: {rid} ({outro}, {path.name})")

        texto = path.read_text(encoding="utf-8")
        for nome, padrao in SEGREDOS.items():
            if re.search(padrao, texto):
                erros.append(f"{path.name}: padrão de segredo — {nome}")

    gh = bool(os.environ.get("GITHUB_ACTIONS"))
    for aviso in avisos:
        print(f"::warning::{aviso}" if gh else f"aviso: {aviso}")
    for erro in erros:
        print(f"::error::{erro}" if gh else f"erro: {erro}", file=sys.stderr)

    print(f"{total} registros em {len(set(donos.values()))} shards; "
          f"{len(erros)} erros, {len(avisos)} avisos")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
