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
MAX_PDF_BYTES = 100 * 1024 * 1024   # provas reais ficam em unidades de MB
MAX_REDIRECTS = 5


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


def _stream_pdf(client, url: str, tmp: Path) -> None:
    """GET em streaming: redirects só para o mesmo host, aborta > MAX_PDF_BYTES."""
    for _ in range(MAX_REDIRECTS + 1):
        with client.stream("GET", url, follow_redirects=False) as r:
            if r.is_redirect and r.has_redirect_location:
                loc = r.url.join(r.headers["location"])
                if loc.host != r.url.host:
                    raise ValueError(f"redirect cross-host recusado: {loc}")
                url = str(loc)
                continue
            r.raise_for_status()
            buf, total = b"", 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    total += len(chunk)
                    if total > MAX_PDF_BYTES:
                        raise ValueError(
                            f"PDF excede {MAX_PDF_BYTES // 2**20} MB: {url}")
                    if len(buf) < 4:
                        buf = (buf + chunk)[:4]
                    f.write(chunk)
            if buf != b"%PDF":
                raise ValueError(f"resposta de {url} não é um PDF")
            return
    raise ValueError(f"redirects demais: {url}")


def baixar(url: str, cache_dir: Path = CACHE_DIR, client=None) -> Path:
    """Baixa um PDF (grátis) com cache em disco."""
    cache_dir = Path(cache_dir)
    dest = cache_path(url, cache_dir)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest = dest.resolve()
    if not dest.is_relative_to(cache_dir.resolve()):
        raise ValueError(f"path de cache fora do diretório: {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    import httpx
    own = client is None
    client = client or httpx.Client(timeout=60,
                                    headers={"User-Agent": USER_AGENT})
    try:
        tmp = dest.with_suffix(dest.suffix + ".part")
        _stream_pdf(client, url, tmp)
        tmp.replace(dest)
    finally:
        if own:
            client.close()
    return dest
