"""Parse Cebraspe multiple-choice prova PDFs (QUESTÃO N + alternativas A-E).

Layout: 'Questão N' marker + <CBM_...> tag; optional base-text block(s);
enunciado = lines between the marker and alternative A, minus deep-indent
citation lines; alternative letters are standalone small elements at column
edge with alternative text indented. ALL-CAPS header lines between items
become each item's `assunto`.

Returns {numero: {'enunciado': str, 'alternativas': [str], 'assunto': str}}.
"""
import re
import subprocess
import html
import xml.etree.ElementTree as ET


def parse_prova(pdf_path, audit=False):
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
