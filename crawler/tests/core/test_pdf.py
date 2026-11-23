"""pdf.py — política de redirect (PER-010) e limpeza de .part (PER-013)."""

from __future__ import annotations

import httpx
import pytest

from crawler import pdf

CDN = "https://cdn.cebraspe.org.br/concursos/PF_24/arquivos"


class _Resp:
    def __init__(self, location=None, chunks=(b"%PDF-teste",)):
        self.url = None  # o _Client preenche com a URL requisitada
        self.is_redirect = self.has_redirect_location = location is not None
        self.headers = {"location": location} if location else {}
        self._chunks = list(chunks)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_bytes(self, _n):
        return iter(self._chunks)


class _Client:
    """Client falso: serve uma sequência de respostas roteirizadas."""

    def __init__(self, *resps):
        self.resps = list(resps)
        self.urls = []

    def stream(self, _m, url, **kw):
        self.urls.append(url)
        r = self.resps.pop(0)
        r.url = httpx.URL(url)
        return r

    def close(self):
        pass


def test_redirect_seguro():
    ok = pdf.redirect_seguro
    assert ok(f"{CDN}/a.pdf", f"{CDN}/b.pdf")                        # mesma origem
    assert ok("http://cdn.cebraspe.org.br/a", "https://cdn.cebraspe.org.br/b")  # upgrade
    assert not ok(f"{CDN}/a", "https://outro.host/b")                # cross-host
    assert not ok(f"{CDN}/a", "http://cdn.cebraspe.org.br/b")        # downgrade https→http
    assert not ok(f"{CDN}/a", "https://cdn.cebraspe.org.br:444/b")   # porta diversa
    assert not ok(f"{CDN}/a", "https://cdn.cebraspe.org.br:443/b")   # porta explícita vs implícita
    assert not ok(f"{CDN}/a", "b")                                   # relativo sem resolver


def test_baixar_segue_redirect_mesmo_host(tmp_path):
    url, nova = f"{CDN}/a.pdf", f"{CDN}/b.pdf"
    cliente = _Client(_Resp(location=nova), _Resp())
    dest = pdf.baixar(url, cache_dir=tmp_path, client=cliente)
    assert cliente.urls == [url, nova]
    assert dest.read_bytes() == b"%PDF-teste"


def test_baixar_recusa_redirect_cross_host(tmp_path):
    cliente = _Client(_Resp(location="https://evil.example/x.pdf"))
    with pytest.raises(ValueError, match="redirect"):
        pdf.baixar(f"{CDN}/a.pdf", cache_dir=tmp_path, client=cliente)
    assert not list(tmp_path.rglob("*.part"))


def test_baixar_recusa_downgrade_https_http(tmp_path):
    cliente = _Client(_Resp(location="http://cdn.cebraspe.org.br/x.pdf"))
    with pytest.raises(ValueError, match="redirect"):
        pdf.baixar(f"{CDN}/a.pdf", cache_dir=tmp_path, client=cliente)
    assert not list(tmp_path.rglob("*.part"))


def test_baixar_aborta_em_redirects_demais(tmp_path):
    cliente = _Client(*(_Resp(location=f"{CDN}/r{i}.pdf") for i in range(10)))
    with pytest.raises(ValueError, match="redirects demais"):
        pdf.baixar(f"{CDN}/a.pdf", cache_dir=tmp_path, client=cliente)


def test_baixar_limpa_part_ao_exceder_teto(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf, "MAX_PDF_BYTES", 4)
    cliente = _Client(_Resp(chunks=[b"%PDF-xxxxx"]))
    with pytest.raises(ValueError, match="excede"):
        pdf.baixar(f"{CDN}/a.pdf", cache_dir=tmp_path, client=cliente)
    assert not list(tmp_path.rglob("*.part"))
