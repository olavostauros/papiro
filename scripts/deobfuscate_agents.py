#!/usr/bin/env python3
"""Materializa os nomes reais de ``.agents/`` a partir do ``.manifest``.

Uso: CI, após ``git crypt unlock`` — o checkout tem os blobs plaintext mas
com nomes ofuscados (``.agents/<8-hex>``); o Dockerfile precisa de
``.agents/prod-agents/auditor.md``. É o equivalente mínimo de
``notes deobfuscate --dir .agents`` para quem só precisa do build context.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1] / ".agents"
HEX = re.compile(r"[0-9a-f]{8}$")


def main() -> int:
    manifest = AGENTS / ".manifest"
    if not manifest.exists():
        print(".agents/.manifest ausente — repo cifrado? (rode git crypt unlock)",
              file=sys.stderr)
        return 1

    feitos = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        nome, _, rel = line.partition("\t")
        if not HEX.fullmatch(nome) or not rel:
            continue
        destino = (AGENTS / rel).resolve()
        if not destino.is_relative_to(AGENTS.resolve()):
            print(f"manifest: path fora de .agents — {rel!r}", file=sys.stderr)
            return 1
        src = AGENTS / nome
        if not src.exists():
            # clone destravado: o path real já existe no lugar do blob
            if destino.exists():
                continue
            print(f"manifest: blob ausente — {nome} ({rel})", file=sys.stderr)
            return 1
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, destino)
        feitos += 1

    print(f".agents: {feitos} paths materializados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
