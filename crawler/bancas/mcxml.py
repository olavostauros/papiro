"""Parser genérico de provas de múltipla escolha: ``pdftohtml -xml`` por
coordenadas (mesma técnica do parser Cebraspe em ``cebraspe/prova.py``).

Cobertura: provas em **duas colunas** com questões numeradas e alternativas
``(A)``–``(E)`` — o layout de FGV e FCC, que ``pdftotext`` (qualquer modo)
embaralha: o texto plano separa os marcadores ``(A)`` do próprio conteúdo ou
entrelaça as colunas na mesma linha. Aqui as linhas visuais são montadas por
(page, coluna, top, left) e consumidas em ordem col0→col1 por página.

A máquina de estados é parametrizada por banca:

- ``qnum``  — texto da linha → número da questão ou ``None``
              (FCC ``"12."``; FGV ``"12"`` solto na margem da coluna)
- ``alt``   — texto → ``(letra, resto)`` ou ``None`` (``(A)``, tolera ``(C))``)
- ``header_re`` — linha que vira ``assunto`` das questões seguintes
- ``stop_re``   — fim da parte objetiva (estudo de caso, redação, rascunho);
              só dispara com questão aberta, para não casar na capa/instruções
- ``noise_re``  — mobiliário de página (cabeçalhos/rodapés que repetem no corpo)

Números espúrios (datas, tabelas) são filtrados pela maior sequência
consecutiva de candidatos na borda — a técnica do ``_ce_modern``.
"""

from __future__ import annotations

import html
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from typing import Callable, Optional, Pattern

QNum = Callable[[str], Optional[tuple]]  # (número, resto da linha → enunciado)
Alt = Callable[[str], Optional[tuple]]


def _xml(pdf_path: str) -> str:
    return subprocess.run(
        ["pdftohtml", "-xml", "-i", "-stdout", str(pdf_path)],
        capture_output=True, text=True).stdout


def _linhas(pdf_path: str, top_cut: float, bottom_cut: float):
    """``(pno, col, top, left, txt, mid)`` — linhas visuais, 2 colunas.

    Alguns PDFs (FCC antiga) têm a flag "no copy": pdftohtml a honra e
    devolve vazio — nesse caso decripta com qpdf (documento público) e
    tenta de novo."""
    out = _xml(pdf_path)
    if not out.strip():
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            if subprocess.run(
                    ["qpdf", "--decrypt", str(pdf_path), tmp.name],
                    capture_output=True).returncode == 0:
                out = _xml(tmp.name)
    root = ET.fromstring(out)
    lines = []
    for page in root.iter("page"):
        pno = int(page.get("number"))
        pw = float(page.get("width"))
        mid = pw / 2
        # heurística 2 colunas: vários elementos começando na faixa logo após
        # o meio da página — margem da coluna direita (FCC ~453-542, FGV ~468)
        two_col = sum(1 for t in page.iter("text")
                      if mid + 5 <= float(t.get("left")) <= mid + 100) >= 4
        for t in page.iter("text"):
            txt = "".join(t.itertext())
            if not txt.strip():
                continue
            top = float(t.get("top"))
            left = float(t.get("left"))
            if top < top_cut or top > bottom_cut:
                continue
            col = 1 if (two_col and left > mid) else 0
            lines.append((pno, col, top, left, txt, mid))
    lines.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

    merged = []
    for pno, col, top, left, txt, mid in lines:
        if (merged and merged[-1][0] == pno and merged[-1][1] == col
                and abs(merged[-1][2] - top) <= 8):
            merged[-1][4].append((left, txt))
        else:
            merged.append([pno, col, top, left, [(left, txt)], mid])
    out = []
    for m in merged:
        parts = sorted(m[4])
        txt = html.unescape(" ".join(t for _, t in parts)).strip()
        out.append((m[0], m[1], m[2], parts[0][0], txt, m[5]))
    return out


def parse_mc(pdf_path, *, qnum: QNum, alt: Alt,
             header_re: Optional[Pattern] = None,
             stop_re: Optional[Pattern] = None,
             noise_re: Optional[Pattern] = None,
             noise_extra: Optional[Pattern] = None,
             qmargin: float = 75.0, amargin: float = 75.0,
             top_cut: float = 62.0, bottom_cut: float = 1205.0,
             audit: bool = False):
    """``{numero: {"enunciado", "alternativas", "assunto"}}`` (+dropped no audit).

    ``qmargin``/``amargin``: distância máxima da margem esquerda da coluna
    para número de questão / marcador de alternativa (col1 usa mid+margem).
    FCC usa margens maiores que FGV — o número fica na margem, mas o
    marcador ``(A)`` é indentado ~35-90pt.

    ``noise_extra``: ruído específico da prova (ex.: banner do cargo que a
    FGV repete no topo de cada página) — o adapter passa a partir do
    ``job``/manifest."""
    lines = _linhas(str(pdf_path), top_cut, bottom_cut)

    # mobiliário: linha idêntica repetida em várias páginas (banner do cargo,
    # cabeçalho/rodapé corrido) — só conta nas faixas de topo/fundo da página:
    # conteúdo legítimo se repete entre questões ("(A) I, apenas.").
    seen_at: dict[str, set] = {}
    for pno, _c, top, _l, txt, _m in lines:
        if top <= top_cut + 60 or top >= bottom_cut - 30:
            seen_at.setdefault(re.sub(r"\s+", " ", txt).strip(), set()).add(pno)
    furniture = {t for t, ps in seen_at.items() if len(ps) >= 4}

    def noisy(txt: str) -> bool:
        return bool((noise_re and noise_re.search(txt))
                    or (noise_extra and noise_extra.search(txt))
                    or re.sub(r"\s+", " ", txt).strip() in furniture)

    def q_edge(col: int, left: float, mid: float) -> bool:
        return left < qmargin or (col == 1 and left < mid + qmargin)

    def a_edge(col: int, left: float, mid: float) -> bool:
        return left < amargin or (col == 1 and left < mid + amargin)

    # pass 1: candidatos a número de questão → maior sequência.
    # Na borda (início de linha) ou no meio da linha mesclada — o XML às
    # vezes junta o fim da questão anterior com "N. Texto".
    mid_qre = re.compile(r"\s(\d{1,3})\.\s+(?=[A-ZÀ-Þ])")
    cand = []
    for pno, col, top, left, txt, mid in lines:
        if noisy(txt):
            continue
        if q_edge(col, left, mid) and (qn := qnum(txt)) is not None:
            cand.append(qn[0])
        else:
            for m in mid_qre.finditer(txt):
                cand.append(int(m.group(1)))
    best: list[int] = []
    run: list[int] = []
    for n in sorted(set(cand)):
        run = run + [n] if run and n == run[-1] + 1 else [n]
        if len(run) > len(best):
            best = run
    valid = set(best)

    # pass 2: máquina de estados
    items: dict[int, dict] = {}
    dropped: list[tuple] = []
    pending_hdr: list[str] = []
    cur_hdr = ""        # seção vigente — persiste até o próximo cabeçalho
    cur = None          # número da questão aberta
    open_hdr = ""       # assunto vigente quando a questão abriu
    buf: list[str] = []  # linhas do enunciado
    alts: dict[str, list[str]] = {}
    cur_alt = None
    in_alt = False
    stopped = False
    prev_hdr = False

    def close_q():
        """Fecha a questão aberta; descasca headers colados no fim da última
        alternativa (cabeçalho de disciplina entre questões) para ``pending_hdr``."""
        nonlocal cur, buf, alts, in_alt, cur_alt
        if cur is not None:
            if header_re and alts:
                last = alts[max(alts)]
                while len(last) > 1 and header_re.match(last[-1]):
                    pending_hdr.insert(0, last.pop())
            items[cur] = {
                "enunciado": re.sub(r"\s+", " ", " ".join(buf)).strip(),
                "alternativas": [re.sub(r"\s+", " ", " ".join(v)).strip()
                                 for _, v in sorted(alts.items())],
                "assunto": open_hdr,
            }
        cur = None
        buf = []
        alts = {}
        in_alt = False
        cur_alt = None

    for pno, col, top, left, txt, mid in lines:
        if noisy(txt):
            dropped.append((pno, col, txt))
            continue
        if stopped:
            dropped.append((pno, col, txt))
            continue
        qn = qnum(txt) if q_edge(col, left, mid) else None
        if qn is None and cur is not None:
            # número válido no meio da linha mesclada: o XML juntou o fim da
            # questão anterior com "N. Texto" (layout compactado da FCC).
            mid_q = re.search(r"\s(\d{1,3})\.\s+(?=[A-ZÀ-Þ])", txt)
            # só o próximo número esperado — "art. 12. O decreto" não é questão
            if mid_q and cur + 1 in valid and int(mid_q.group(1)) == cur + 1:
                head = txt[:mid_q.start()].strip()
                if head:
                    (alts[cur_alt] if in_alt else buf).append(head)
                txt = txt[mid_q.start() + 1:]
                qn = qnum(txt)
        if qn is not None and qn[0] in valid:
            close_q()
            if pending_hdr:
                cur_hdr = " ".join(pending_hdr)
                pending_hdr = []
            open_hdr = cur_hdr
            cur = qn[0]
            if qn[1]:
                buf.append(qn[1])
            continue
        if cur is not None and stop_re and stop_re.search(txt):
            close_q()
            stopped = True
            dropped.append((pno, col, "STOP:" + txt))
            continue
        am = alt(txt) if a_edge(col, left, mid) else None
        if am and cur is not None:
            letter, rest = am
            if letter == chr(ord("A") + len(alts)):
                in_alt = True
                cur_alt = letter
                alts[letter] = [rest] if rest else []
                continue
        if cur is None:
            if header_re and header_re.match(txt):
                if not prev_hdr:
                    pending_hdr = []   # título de seção isolado → substitui
                pending_hdr.append(txt)
                prev_hdr = True
            else:
                prev_hdr = False
            dropped.append((pno, col, txt))
            continue
        if in_alt:
            alts[cur_alt].append(txt)
        else:
            buf.append(txt)
    close_q()

    if audit:
        return items, dropped
    return items


# ---------------------------------------------------------------------------
# configurações por banca
# ---------------------------------------------------------------------------

def _qnum_fgv(txt: str) -> Optional[tuple]:
    m = re.fullmatch(r"\d{1,3}", txt)
    return (int(m.group(0)), "") if m else None


def _qnum_fcc(txt: str) -> Optional[tuple]:
    """``12.`` ou ``12. Texto do enunciado…`` — número e início dividem a linha.
    O resto pode trazer o divisor ``___`` colado pelo merge de linhas."""
    m = re.match(r"^(\d{1,3})\.\s*(.*)$", txt)
    if not m:
        return None
    rest = re.sub(r"\s*[_ ]{10,}$", "", m.group(2)).strip()
    return (int(m.group(1)), rest)


def _alt_paren(txt: str) -> Optional[tuple]:
    """``(A) texto`` → ("A", "texto"); tolera ``(A))``, ``(A) )`` e ``( A )``."""
    m = re.match(r"^\(\s*([A-E])\s*(?:\)\s*)+\.?\s*(.*)$", txt)
    return (m.group(1), m.group(2).strip()) if m else None


FGV = dict(
    qnum=_qnum_fgv,
    alt=_alt_paren,
    # cabeçalho de disciplina FGV: "Língua Portuguesa", "Comércio Exterior",
    # "Administração Aduaneira e Modelo de Controle - MCA" (linha curta,
    # Title-Case, sem ponto final — nunca termina em '.' e tem < 90 chars)
    header_re=re.compile(
        r"^[A-ZÀ-Þ][^.!?;]{4,90}$"),
    stop_re=re.compile(
        r"(?i)folha de rascunho|rascunho|prova discursiva|estudo de caso|"
        r"reda[çc][ãa]o|dissertativa"),
    noise_re=re.compile(
        r"(?i)fgv conhecimento|tipo\s*[-–—]?\s*branca|p[aá]gina\s+\d+|"
        r"receita federal do brasil \(curso|sua prova|informa[çc][õo]es gerais|"
        r"concurso p[úu]blico\s*$"),
)

FCC = dict(
    qnum=_qnum_fcc,
    alt=_alt_paren,
    # número na margem (l~53/474); marcador (A) indentado (l~87/508, até ~121/542)
    qmargin=60.0, amargin=130.0,
    # questões de topo de coluna começam em top≈52 — abaixo do corte default
    top_cut=40.0,
    # seções FCC são ALL-CAPS: "CONHECIMENTOS GERAIS", "LÍNGUA PORTUGUESA",
    # "LEGISLAÇÃO ESPECÍFICA"…
    header_re=re.compile(r"^[A-ZÀ-Þ][A-ZÀ-Þ0-9 ,()\-/]{5,}$"),
    stop_re=re.compile(
        r"(?i)estudo de caso|prova dissertativa|dissertativa|pe[çc]a\b|"
        r"reda[çc][ãa]o|folha de respostas"),
    noise_re=re.compile(
        r"(?i)funda[çc][ãa]o carlos chagas|caderno de prova|"
        r"n[ºo] de inscri[çc][ãa]o|assinatura|BCENT|_+ Caderno|"
        r"\d{2}/\d{2}/\d{2}\s*-\s*\d{2}:\d{2}|^[_ ]{10,}$|"
        r"(?-i:\bMODELO\b)"),  # selo do caderno — "modelo" miúdo é conteúdo
)
