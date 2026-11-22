"""Parse Cebraspe certo/errado prova PDFs into {numero: enunciado} using
pdftohtml -xml coordinates.

Two-column aware: item numbers sit at the column edge, item text is
indented; items are tight paragraphs separated from comandos/base text.

variant="modern" (default, post-2021 provas): item number is a separate
edge-aligned element at the START of the item's first line; gate parsing on
the PROVA OBJETIVA / CONHECIMENTOS marker; JUSTIFICATIVA..FimJust blocks
skipped; spurious edge numbers filtered by keeping only the longest run of
consecutive item numbers.

variant="old" (PF_18-era provas): base text sits in the left column with
lone line-number markers at the column edge; the item number merges at the
END of the item's first line ("texto do item 42"). Item-start lines must
have non-empty text before the number; lone-number lines are ignored; a
line matching a comando pattern closes the current item.
"""
import re
import subprocess
import html
import xml.etree.ElementTree as ET

START_RE = re.compile(r"PROVA OBJECTIVA|PROVA OBJETIVA|CONHECIMENTOS"
                      r"|FASE\s+\w+\s+OBJETIVA", re.I)

CMD_RE = re.compile(
    r"(?i)^\s*(julgue|com base|considerando|acerca|em rela|a respeito|no que se|"
    r"à luz|de acordo|a partir|tendo como|em cada um|com relação|nos itens|"
    r"a propósito|no caso|na situação hipotética|supondo|admita|assuma|figura|"
    r"tabela|o quadro|a tabela|o gráfico|a figura|o esquema|o mapa|o texto)")


def _merged_lines(pdf_path, gate=True):
    out = subprocess.run(
        ["pdftohtml", "-xml", "-i", "-stdout", pdf_path],
        capture_output=True, text=True).stdout
    root = ET.fromstring(out)
    lines = []
    started = not gate
    for page in root.iter("page"):
        pno = int(page.get("number"))
        pw = float(page.get("width"))
        mid = pw / 2
        # two-column iff right-column line starts (left ~455-500) are common;
        # single-column pages just have scattered mid-line elements past mid
        col1_starts = sum(1 for t in page.iter("text")
                          if 450 <= float(t.get("left")) <= 500)
        two_col = col1_starts >= 4
        for t in page.iter("text"):
            top = float(t.get("top"))
            left = float(t.get("left"))
            txt = "".join(t.itertext())
            if not txt.strip():
                continue
            if not started:
                if START_RE.search(txt):
                    started = True
                else:
                    continue
            if top < 62 or top > 1225:  # header/footer zone
                continue
            col = 1 if (two_col and left > mid) else 0
            lines.append((pno, col, top, left, txt))
    lines.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

    merged = []
    for pno, col, top, left, txt in lines:
        if (merged and merged[-1][0] == pno and merged[-1][1] == col
                and abs(merged[-1][2] - top) <= 8):
            merged[-1][4].append((left, txt))
        else:
            merged.append([pno, col, top, left, [(left, txt)]])
    for m in merged:
        parts = sorted(m[4])
        m[3] = parts[0][0]
        m[4] = html.unescape(" ".join(t for _, t in parts)).strip()
    return merged


def _is_edge(col, left):
    return left < 60 or (col == 1 and left < 475)


def parse_prova(pdf_path, variant="modern", gate=True, audit=False):
    merged = _merged_lines(pdf_path, gate=gate)
    if variant == "old":
        items, dropped = _parse_old(merged)
    else:
        items, dropped = _parse_modern(merged)
    if audit:
        return items, dropped
    return items


def _strip_justificativas(merged):
    """Remove JUSTIFICATIVA blocks from merged lines.

    Prova+gabarito-preliminar combined docs print a "JUSTIFICATIVA - Certo."
    paragraph after each item. Some files close the block with a FimJust
    marker, others don't, and a single file can mix both. Positional rule:
    justification continuations are indented like item text, so the block
    runs until the next edge-positioned line (item number / comando / base
    text) or a line containing FimJust.
    """
    out = []
    skipping = False
    for pno, col, top, left, txt in merged:
        if skipping:
            if _is_edge(col, left) or "FimJust" in txt:
                skipping = False
            else:
                continue
        if "FimJust" in txt:
            continue
        if txt.lstrip().startswith("JUSTIFICATIVA"):
            skipping = True
            continue
        out.append((pno, col, top, left, txt))
    return out


def _parse_modern(merged):
    item_re = re.compile(r"^(\d{1,3})(?:\s+(.*)|\s*$)")
    merged = _strip_justificativas(merged)

    # pass 1: candidate item numbers in encounter order
    candidates = []
    for pno, col, top, left, txt in merged:
        if not txt:
            continue
        m = item_re.match(txt)
        if m and _is_edge(col, left):
            candidates.append(int(m.group(1)))

    # longest chain of consecutive numbers = the real item sequence.
    # Order-independent: column sorting can reorder item numbers across
    # pages, so find the longest consecutive run in sorted order.
    best = cur = []
    for n in sorted(set(candidates)):
        cur = cur + [n] if cur and n == cur[-1] + 1 else [n]
        if len(cur) > len(best):
            best = cur
    valid = set(best)

    # pass 2: assemble items
    items = {}
    dropped = []
    cur_num = None
    last_top = None
    for pno, col, top, left, txt in merged:
        if not txt:
            continue
        m = item_re.match(txt)
        if m and _is_edge(col, left) and int(m.group(1)) in valid:
            n = int(m.group(1))
            rest = (m.group(2) or "").strip()
            if not rest and items.get(n):
                continue  # answer-grid echo (folha de rascunho etc.)
            cur_num = n
            items[n] = []
            if rest:
                items[n].append(rest)
            last_top = top
            continue
        if cur_num is None:
            dropped.append((pno, col, txt))
            continue
        indented = (58 <= left < 78) if col == 0 else (468 <= left < 496)
        close = (top - last_top) <= 40
        if indented and close:
            items[cur_num].append(txt)
            last_top = top
        else:
            dropped.append((pno, col, txt))
            cur_num = None
    items = {n: re.sub(r"\s+", " ", " ".join(p)).strip()
             for n, p in items.items() if p}
    return items, dropped


def _parse_old(merged):
    items = {}
    dropped = []
    last_n = 0
    last_top = None
    last_col = 0
    cur_open = False
    for pno, col, top, left, txt in merged:
        if not txt:
            continue
        m = re.match(r"^(.*\S)\s+(\d{1,3})$", txt)
        edge = left < 80 or (col == 1 and left < 500)
        if m and edge and int(m.group(2)) == last_n + 1 and len(m.group(1)) > 15:
            n = int(m.group(2))
            last_n = n
            items[n] = [m.group(1).strip()]
            last_top = top
            cur_open = True
            last_col = col
            continue
        if not cur_open:
            dropped.append((last_n, pno, col, txt))
            continue
        indented = left >= (60 if col == 0 else 470)
        close = (top - last_top) < 30 or col != last_col
        if re.match(r"^\d{1,2}$", txt):
            continue  # lone line-number marker from base text
        if CMD_RE.match(txt):
            cur_open = False
            dropped.append((last_n, pno, col, "CMD:" + txt))
            continue
        if indented and close:
            items[last_n].append(txt)
            last_top = top
            last_col = col
        else:
            cur_open = False
            dropped.append((last_n, pno, col, txt))
    items = {n: re.sub(r"\s+", " ", " ".join(p)).strip()
             for n, p in items.items() if p}
    return items, dropped
