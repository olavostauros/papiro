"""Gabarito definitivo Cebraspe: download + parse local com ``pdftotext -layout``.

Grátis e exato (sem Firecrawl). O PDF é uma tabela de linhas pareadas::

    Item      1   2   3   4 ...          (ou "Questão" em múltipla escolha)
    Gabarito  C   E   X   C ...          (C/E, ou letras A–E; X = anulado)

Em provas de múltipla escolha as letras costumam vir grudadas
("CCDADBB…") e a linha de respostas pode cair na linha seguinte ao rótulo
"Gabarito"; células vazias da tabela aparecem como ``0`` e são descartadas.

``X`` = item anulado: fica em ``Gabarito.anulados`` e não deve virar registro.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "pdf"
USER_AGENT = "papiro-crawler/0.1 (+https://olavostauros.github.io/papiro/)"

_HEADER = re.compile(r"^\s*(Item|Itens|Quest\w*)\b\s*(.*)$", re.I)
_ANSWER = re.compile(r"^\s*Gabarito\b\s*(.*)$", re.I)


class GabaritoError(ValueError):
    """O PDF não tem o formato de gabarito esperado."""


@dataclass
class Gabarito:
    respostas: dict[int, str]          # numero → "C" | "E" | "X" | "A".."E"
    url: str = ""
    codigo: Optional[str] = None       # ex.: 057_IBAMA_CB1_01, quando impresso
    avisos: list[str] = field(default_factory=list)

    @property
    def itens(self) -> list[int]:
        return sorted(self.respostas)

    @property
    def anulados(self) -> list[int]:
        return sorted(n for n, r in self.respostas.items() if r == "X")

    @property
    def tipo(self) -> Literal["certo_errado", "multipla_escolha"]:
        letras = {r for r in self.respostas.values() if r != "X"}
        return "certo_errado" if letras <= {"C", "E"} else "multipla_escolha"

    def para_dataset(self, numero: int,
                     tipo: Optional[str] = None) -> Optional[str]:
        """Converte para o formato de ``to_questao`` (None se anulado/ausente)."""
        r = self.respostas.get(numero)
        if r is None or r == "X":
            return None
        if (tipo or self.tipo) == "certo_errado":
            return {"C": "certo", "E": "errado"}.get(r)
        return r.lower()


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


def parse_text(text: str, url: str = "") -> Gabarito:
    lines = text.splitlines()
    respostas: dict[int, str] = {}
    avisos: list[str] = []
    codigo = None
    m = re.search(r"\b(?:MATRIZ_)?(\d{3}_?[A-Z][A-Z0-9_]*_\d{2,3}(?:_\d{2})?)\b", text, re.I)
    if m:
        codigo = m.group(1)

    i = 0
    while i < len(lines):
        h = _HEADER.match(lines[i])
        if not h:
            i += 1
            continue
        nums = [int(x) for x in re.findall(r"\d+", h.group(2))]
        # acha a linha "Gabarito" seguinte (antes do próximo cabeçalho)
        j, answers = i + 1, None
        while j < len(lines) and not _HEADER.match(lines[j]):
            a = _ANSWER.match(lines[j])
            if a:
                rest = a.group(1)
                k = j
                while not re.search(r"[A-EX]", rest) and k + 1 < len(lines) \
                        and not _HEADER.match(lines[k + 1]):
                    k += 1
                    rest = lines[k] if lines[k].strip() else rest
                answers = re.findall(r"[A-EX0]", rest.upper())
                j = k
                break
            j += 1
        if answers is None:
            i += 1
            continue
        pares = [(n, r) for n, r in zip(nums, answers) if n != 0]
        reais = [n for n in nums if n != 0]
        if len(answers) < len(reais):
            raise GabaritoError(
                f"linha de itens com {len(reais)} números mas {len(answers)} respostas "
                f"(itens {reais[:3]}…)")
        for n, r in pares:
            if r == "0":
                raise GabaritoError(f"item {n} sem resposta na tabela")
            if n in respostas and respostas[n] != r:
                raise GabaritoError(f"item {n} aparece duas vezes com respostas diferentes")
            respostas[n] = r
        i = j + 1

    if not respostas:
        raise GabaritoError("nenhuma tabela Item/Gabarito encontrada")
    nums = sorted(respostas)
    buracos = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
    if buracos:
        avisos.append(f"itens ausentes no gabarito: {buracos[:10]}")
    return Gabarito(respostas=respostas, url=url, codigo=codigo, avisos=avisos)


def parse_pdf(pdf: Path, url: str = "") -> Gabarito:
    return parse_text(pdf_to_text(pdf), url=url)


def cache_path(url: str, cache_dir: Path = CACHE_DIR) -> Path:
    m = re.search(r"/concursos/([^/]+)/arquivos/([^/?#]+)", url)
    if m:
        return cache_dir / m.group(1) / m.group(2)
    return cache_dir / re.sub(r"[^A-Za-z0-9_.-]+", "_", url)[-120:]


def baixar(url: str, cache_dir: Path = CACHE_DIR, client=None) -> Path:
    """Baixa um PDF do CDN da Cebraspe (grátis) com cache em disco."""
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
            raise GabaritoError(f"resposta de {url} não é um PDF")
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(r.content)
        tmp.replace(dest)
    finally:
        if own:
            client.close()
    return dest


def carregar(url: str, cache_dir: Path = CACHE_DIR) -> Gabarito:
    """Baixa (com cache) e parseia o gabarito definitivo de ``url``."""
    return parse_pdf(baixar(url, cache_dir), url=url)


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        g = carregar(arg) if arg.startswith("http") else parse_pdf(Path(arg), url=arg)
        print(f"{arg}: {len(g.itens)} itens ({g.itens[0]}–{g.itens[-1]}), tipo={g.tipo}, "
              f"anulados={g.anulados}, codigo={g.codigo}, avisos={g.avisos}")
