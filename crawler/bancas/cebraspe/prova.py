"""Parser autoritativo de provas Cebraspe: ``pdftohtml -xml`` por coordenadas.

Dois layouts:

- ``tipo="ce"`` (certo/errado) — número do item na borda da coluna, texto
  recuado. ``variant="modern"`` (pós-2021): o número é um elemento separado
  no INÍCIO da primeira linha do item; gate no marcador PROVA OBJETIVA /
  CONHECIMENTOS; blocos JUSTIFICATIVA..FimJust ignorados; números espúrios
  filtrados pela maior sequência consecutiva. ``variant="old"`` (era
  PF_18): texto-base na coluna esquerda com marcadores soltos de linha; o
  número do item aparece no FIM da primeira linha ("texto do item 42").
- ``tipo="mc"`` — marcador "Questão N" (+ tag <CBM_…>), alternativas A–E
  com a letra num elemento pequeno na borda; linhas ALL-CAPS entre itens
  viram o ``assunto`` de cada questão.

Cada item retorna ``{"enunciado", "alternativas", "assunto"}``; convenção do
dataset: enunciado = só o item (sem texto-base nem comando). Com
``audit=True`` retorna ``(itens, dropped)`` — as linhas descartadas vão para
``dropped_<key>.txt`` na auditoria do job.
"""
import html
import re
import subprocess
import xml.etree.ElementTree as ET

START_RE = re.compile(r"PROVA OBJECTIVA|PROVA OBJETIVA|CONHECIMENTOS"
                      r"|FASE\s+\w+\s+OBJETIVA", re.I)

CMD_RE = re.compile(
    r"(?i)^\s*(julgue|com base|considerando|acerca|em rela|a respeito|no que se|"
    r"à luz|de acordo|a partir|tendo como|em cada um|com relação|nos itens|"
    r"a propósito|no caso|na situação hipotética|supondo|admita|assuma|figura|"
    r"tabela|o quadro|a tabela|o gráfico|a figura|o esquema|o mapa|o texto)")


def parse_prova(pdf_path, tipo="ce", variant="modern", audit=False):
    """Ponto de entrada do adapter: {numero: {enunciado, alternativas, assunto}}."""
    if tipo == "mc":
        return _parse_mc(str(pdf_path), audit=audit)
    res = _parse_ce(str(pdf_path), variant=variant, audit=audit)
    if audit:
        its, dropped = res
        return {n: {"enunciado": t, "alternativas": ["Certo", "Errado"],
                    "assunto": ""} for n, t in its.items()}, dropped
    return {n: {"enunciado": t, "alternativas": ["Certo", "Errado"],
                "assunto": ""} for n, t in res.items()}


# ---------------------------------------------------------------------------
# certo/errado (items.py)
# ---------------------------------------------------------------------------

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


def _parse_ce(pdf_path, variant="modern", gate=True, audit=False):
    merged = _merged_lines(pdf_path, gate=gate)
    if variant == "old":
        items, dropped = _ce_old(merged)
    else:
        items, dropped = _ce_modern(merged)
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


def _ce_modern(merged):
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


def _ce_old(merged):
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


# ---------------------------------------------------------------------------
# múltipla escolha (mc.py)
# ---------------------------------------------------------------------------

def _parse_mc(pdf_path, audit=False):
    out = subprocess.run(["pdftohtml", "-xml", "-i", "-stdout", pdf_path],
                         capture_output=True, text=True).stdout
    root = ET.fromstring(out)
    lines = []
    started = False
    for page in root.iter("page"):
        pno = int(page.get("number"))
        pw = float(page.get("width"))
        mid = pw / 2
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
                if ("OBJETIVA" in txt or "CONHECIMENTOS" in txt
                        or "quest" in txt.lower()):
                    started = True
                else:
                    continue
            if top < 62 or top > 1205:
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
        m.append(parts)

    tag_re = re.compile(r"\s*<[A-Z][A-Z_0-9]*>\s*")
    quest_re = re.compile(r"^[Qq][Uu][Ee][Ss][Tt][ÃãAa][Oo]\s+(\d+)")
    alt_re = re.compile(r"^([A-E])(?:\s+(.*)|\s*$)")
    header_re = re.compile(r"^[A-ZÀ-Þ][A-ZÀ-Þ0-9 ,()\-]{7,}$")
    end_just_re = re.compile(r"\*\s*/")
    livre_re = re.compile(r"[•·\-\s]*espa[çc]o\s+livre[.\s]*")

    def edge(col, left):
        return left < 60 or (col == 1 and left < 475)

    def indent(col, left):
        return left >= (58 if col == 0 else 470)

    items = {}
    dropped = []
    cur_header = ""
    pending_hdr = []
    cur = None
    buf = []            # lines between 'Questão N' and alt A: (top, txt, left, col)
    in_alt = False
    cur_alt = None
    last_top = None
    in_justif = False   # inside '||A|| - ... */' justification block

    def close_item():
        """Enunciado = buf lines after the last deep-indent citation line.

        Base-text citations are centered/indented (>=120 col0, >=530 col1);
        enunciado paragraphs and comando lines sit at the column edge or at
        paragraph indent (<120/<530).
        """
        if cur is None or not items.get(cur):
            return
        start = 0
        for i, (_, _, lft, c) in enumerate(buf):
            if (c == 0 and lft >= 120) or (c == 1 and lft >= 530):
                if i < len(buf) - 1:
                    start = i + 1
        enun = re.sub(r"\s+", " ", " ".join(t for _, t, _, _ in buf[start:])).strip()
        items[cur]["enunciado"] = enun
        buf.clear()

    for pno, col, top, left, txt, parts in merged:
        txt = tag_re.sub("", txt).strip()
        if not txt:
            continue
        # 'FimDoTexto' end-of-base-text marker can merge with the next
        # 'Questão N' on the same PDF line — strip it to recover the item.
        txt = re.sub(r"^FimDoTexto\s*", "", txt)
        if not txt:
            continue
        qm = quest_re.match(txt)
        if qm:
            if cur is not None and not in_alt:
                close_item()
            rem = tag_re.sub("", txt[qm.end():]).strip()
            if rem and header_re.match(rem):
                pending_hdr.append(rem)
                cur_header = " ".join(pending_hdr)
            cur = int(qm.group(1))
            # stray-glyph marker like 'Questão 344' for item 34 (duplicate
            # text layer) — trim trailing digits back to the expected number
            if items:
                expected = max(items) + 1
                while cur != expected and len(str(cur)) > 1 \
                        and str(cur).startswith(str(expected)):
                    cur = int(str(cur)[:-1])
            items[cur] = {"enunciado": "", "alternativas": {},
                          "assunto": cur_header}
            pending_hdr = []
            buf = []
            in_alt = False
            cur_alt = None
            last_top = top
            in_justif = False
            continue
        if in_justif:
            if end_just_re.search(txt):
                in_justif = False
            dropped.append((pno, col, txt))
            continue
        if txt.startswith("||"):
            if not end_just_re.search(txt):
                in_justif = True
            dropped.append((pno, col, txt))
            continue
        if cur is None:
            dropped.append((pno, col, txt))
            if header_re.match(txt):
                pending_hdr.append(txt)
                cur_header = " ".join(pending_hdr)
            else:
                pending_hdr = []
            continue
        if livre_re.fullmatch(txt.lower()):
            continue
        first_is_letter = parts and re.fullmatch(r"[A-E]", parts[0][1].strip())
        am = alt_re.match(txt)
        if (first_is_letter and edge(col, left) and am
                and (len(parts) == 1
                     or any(lft >= (58 if col == 0 else 470)
                            for lft, _ in parts[1:]))):
            letter = am.group(1)
            nxt = chr(ord("A") + len(items[cur]["alternativas"]))
            if letter == "A" and not in_alt and not buf:
                pass  # lone 'A' at enunciado start (e.g. 'A Lei n.º ...')
            elif letter != nxt and (cands := [
                    n for n, it in items.items()
                    if n != cur and 0 < len(it["alternativas"]) < 5
                    and chr(ord("A") + len(it["alternativas"])) == letter]):
                # 'Float' item: alternatives continue after another item's
                # block (seen in CAESB page breaks) — resume the unique
                # earlier item that is missing exactly this alternative.
                if len(cands) == 1:
                    cur = cands[0]
                    in_alt = True
                    cur_alt = letter
                    items[cur]["alternativas"][letter] = []
                    rest = (am.group(2) or "").strip()
                    if rest:
                        items[cur]["alternativas"][letter].append(rest)
                    last_top = top
                    continue
            elif letter == nxt:
                if not in_alt and letter == "A":
                    close_item()
                in_alt = True
                cur_alt = letter
                items[cur]["alternativas"][letter] = []
                rest = (am.group(2) or "").strip()
                if rest:
                    items[cur]["alternativas"][letter].append(rest)
                last_top = top
                continue
        if not in_alt:
            buf.append((top, txt, left, col))
        else:
            if header_re.match(txt):
                dropped.append((pno, col, txt))
                pending_hdr.append(txt)
                cur_header = " ".join(pending_hdr)
            elif indent(col, left) and 0 <= (top - last_top) < 34:
                items[cur]["alternativas"][cur_alt].append(txt)
                last_top = top
            else:
                dropped.append((pno, col, txt))
                if header_re.match(txt):
                    pending_hdr.append(txt)
                    cur_header = " ".join(pending_hdr)
                else:
                    pending_hdr = []

    if cur is not None and not in_alt:
        close_item()

    res = {}
    for n, it in items.items():
        alts = [re.sub(r"\s+", " ", " ".join(t)).strip()
                for l, t in sorted(it["alternativas"].items())]
        res[n] = {"enunciado": it["enunciado"], "alternativas": alts,
                  "assunto": it.get("assunto", "")}
    if audit:
        return res, dropped
    return res
