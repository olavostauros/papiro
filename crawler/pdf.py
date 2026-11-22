"""Download + cache local de PDFs e texto via poppler (grátis, sem Firecrawl).

``baixar`` cacheia por URL em ``crawler/.cache/pdf/`` (volume no compose —
re-execuções não rebaixam). ``pdf_to_text``/``pdftotext_bin`` são o wrapper
de ``pdftotext -layout`` usado por gabaritos e pelo parser secundário.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "pdf"
USER_AGENT = "papiro-crawler/0.1 (+https://olavostauros.github.io/papiro/)"


def pdftotext_bin() -> str:
    found = shutil.which("pdftotext")
    if found:
        return found
    for cand in (r"C:\Program Files\Git\mingw64\bin\pdftotext.exe",
                 "/mingw64/bin/pdftotext", "/usr/bin/pdftotext"):
        if Path(cand).exists():
            return cand
    raise FileNotFoundError("pdftotext (poppler) não encontrado no PATH")


def pdf_to_text(pdf: Path) -> str:
    out = subprocess.run([pdftotext_bin(), "-layout", "-enc", "UTF-8", str(pdf), "-"],
                         capture_output=True, check=True)
    return out.stdout.decode("utf-8", errors="replace")


def pdf_to_text_plain(pdf: Path) -> str:
    """Texto corrido (sem -layout), para conferir trechos no PDF."""
    out = subprocess.run([pdftotext_bin(), "-enc", "UTF-8", str(pdf), "-"],
                         capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace")


def contar_paginas(pdf: Path) -> int:
    return max(1, pdf_to_text(pdf).count("\f"))


def cache_path(url: str, cache_dir: Path = CACHE_DIR) -> Path:
    m = re.search(r"/concursos/([^/]+)/arquivos/([^/?#]+)", url)
    if m:
        return cache_dir / m.group(1) / m.group(2)
    return cache_dir / re.sub(r"[^A-Za-z0-9_.-]+", "_", url)[-120:]


def baixar(url: str, cache_dir: Path = CACHE_DIR, client=None) -> Path:
    """Baixa um PDF (grátis) com cache em disco."""
    dest = cache_path(url, cache_dir)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    import httpx
    own = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True,
                                    headers={"User-Agent": USER_AGENT})
    try:
        r = client.get(url)
        r.raise_for_status()
        if not r.content.startswith(b"%PDF"):
            raise ValueError(f"resposta de {url} não é um PDF")
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(r.content)
        tmp.replace(dest)
    finally:
        if own:
            client.close()
    return dest
