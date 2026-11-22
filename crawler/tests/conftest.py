"""Testes NUNCA gastam crédito nem acessam a rede.

- ``crawler.extract.make_app`` é substituído por uma função que falha.
- Qualquer requisição httpx falha (fixtures locais em ``fixtures/``).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _sem_rede_nem_credito(monkeypatch):
    import httpx

    def bloqueado(*a, **k):
        raise RuntimeError("teste tentou acessar a rede/Firecrawl")

    monkeypatch.setattr(httpx.Client, "send", bloqueado)
    monkeypatch.setattr(httpx.AsyncClient, "send", bloqueado)
    try:
        import crawler.extract as ext
        monkeypatch.setattr(ext, "make_app", bloqueado)
        monkeypatch.setattr(ext, "extract_prova", bloqueado)
    except ImportError:  # firecrawl não instalado: nada a bloquear
        pass


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def evento():
    def load(nome: str) -> dict:
        return json.loads((FIXTURES / "eventos" / f"{nome}.json").read_text(encoding="utf-8"))
    return load


@pytest.fixture
def fake_fetch():
    """Fetch que responde a partir das fixtures da API."""
    from crawler.bancas.cebraspe.api import API, LIST_URL

    def fetch(url: str):
        if url == LIST_URL:
            return json.loads((FIXTURES / "api_lista.json").read_text(encoding="utf-8"))
        nome = url.removeprefix(API + "/")
        return json.loads((FIXTURES / "eventos" / f"{nome}.json").read_text(encoding="utf-8"))
    return fetch


requires_pdftotext = pytest.mark.skipif(
    shutil.which("pdftotext") is None
    and not Path(r"C:\Program Files\Git\mingw64\bin\pdftotext.exe").exists(),
    reason="pdftotext (poppler) indisponível",
)
