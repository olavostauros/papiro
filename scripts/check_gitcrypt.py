#!/usr/bin/env python3
"""Todo blob rastreado sob ``.agents/`` deve ser ciphertext git-crypt.

Lê o índice (``git ls-files -s`` + ``git cat-file blob``), não o working
tree — funciona igual em clones destravados (host/VM, onde os arquivos em
disco são plaintext) e no checkout do CI (que não tem a chave). Um blob sem
o magic ``\\x00GITCRYPT`` é plaintext prestes a vazar para o repo público.
"""

from __future__ import annotations

import subprocess
import sys

MAGIC = b"\x00GITCRYPT"


def main() -> int:
    ls = subprocess.run(
        ["git", "ls-files", "-s", "--", ".agents"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    total = 0
    plaintext: list[str] = []
    for line in ls.splitlines():
        meta, _, path = line.partition("\t")
        if not meta or not path:
            continue
        sha = meta.split()[1]
        blob = subprocess.run(
            ["git", "cat-file", "blob", sha], check=True, capture_output=True
        ).stdout
        total += 1
        if not blob.startswith(MAGIC):
            plaintext.append(path)

    for path in plaintext:
        print(f".agents: blob NÃO cifrado — {path}", file=sys.stderr)
    if plaintext:
        return 1
    print(f".agents: {total} blobs verificados, todos git-crypt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
