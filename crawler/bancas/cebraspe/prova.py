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

Cada item retorna ``{"enunciado", "alternativas", "assunto", "texto"}``;
convenção do dataset: enunciado = só o item (sem texto-base nem comando).
Blocos ``Texto <ref>`` são coletados à parte: ``item["texto"]`` carrega
``{"ref", "conteudo", "citacao", "imagem"}`` — por rótulo citado no enunciado
quando existe, posicional senão (último texto antes do item). Com
``audit=True`` retorna ``(itens, dropped)`` — as linhas descartadas vão para
``dropped_<key>.txt`` na auditoria do job (o texto-base continua nelas).
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

# --- texto-base -------------------------------------------------------------
# "Texto CG1A1" abre bloco; fecha no próximo marcador de item/questão, comando,
# cabeçalho de seção ou outro "Texto". A citação bibliográfica do fim tem fonte
# menor que o corpo; quando o texto é imagem o bloco fica vazio e flaga.
_TEXTO_HEAD_RE = re.compile(r"^Textos?\b")
_TEXTO_REF_RE = re.compile(r"^Textos?\s+([A-Z]{1,5}\d[A-Z]?\d*|[IVX]{1,4})\b",
                           re.I)
_ENUN_REF_RE = re.compile(r"textos?\s+([A-Z]{1,5}\d[A-Z]?\d*)", re.I)
# remissão genérica ("o texto", "no texto") — ignora "texto legal" & cia.
_REF_GENERICO_RE = re.compile(
    r"\btextos?\b(?!\s+(?:constitucional|legal|normativ\w*|"
    r"da\s+lei|d[oe]\s+c[oó]digo|da\s+constitui[cç][aã]o))", re.I)
_CIT_RE = re.compile(
    r"(?i)\b(?:In:|Dispon[íi]vel\b|Fonte\s*:|Acesso em|adaptad|extra[íi]d[oa]|"
    r"apud\b|Internet\b)")
# material-base citado num bloco solto entre itens ("o texto acima",
# "a figura seguinte", "a tabela CB1A2") — promove o buffer a texto.
_BASE_REF_RE = re.compile(
    r"\b(?:texto|textual|texts?|figur\w*|quadro|tabela|gr[áa]fic\w*|"
    r"esquema|mapa|charge|tirinha|cartum|poema|cr[oô]nica|m[úu]sica|"
    r"propaganda|an[úu]ncio|ilustra\w*|fluxograma|diagrama)\b", re.I)
_BASE_IMG_RE = re.compile(
    r"\b(?:figur\w*|quadro|tabela|gr[áa]fic\w*|esquema|mapa|charge|"
    r"tirinha|cartum|propaganda|an[úu]ncio|ilustra\w*|fluxograma|"
    r"diagrama|imagem)\b", re.I)
_CMD_TAIL_RE = re.compile(
    r"\b(?:julgue|assinale|marque|responda|indique|aponte|de acordo|"
    r"com rela|a respeito|considerando|com base|a partir|em rela|"
    r"no que se|acerca|a prop[oó]sito|tendo em vista|tendo como|"
    r"according|judge|based on|no que diz)\b", re.I)
_SEP_RE = re.compile(r"^[\-–—=*\s]{2,}$")


def _texto_head(txt):
    """'Texto CG1A1' → 'CG1A1'; 'Texto para os itens…' → ''; senão None."""
    if len(txt) > 90 or not _TEXTO_HEAD_RE.match(txt):
        return None
    m = _TEXTO_REF_RE.match(txt)
    return m.group(1).upper() if m else ""


def _font_sizes(root):
    return {fs.get("id"): float(fs.get("size"))
            for fs in root.iter("fontspec") if fs.get("size")}


def _images_by_page(root):
    """{page: [(top, height)]} — detecção de texto-base em imagem."""
    out = {}
    for page in root.iter("page"):
        imgs = [(float(i.get("top")), float(i.get("height") or 0))
                for i in page.iter("image")]
        if imgs:
            out[int(page.get("number"))] = imgs
    return out


def _finish_texto(block, images):
    """{ref, lines:[(txt,size,left,col)], pno, top} → dict ou None.

    Separa a citação final (sufixo em fonte menor ou padrão bibliográfico),
    reconstrói parágrafos pelo recuo de primeira linha e marca ``imagem``
    quando o bloco ficou vazio mas há <image> na faixa seguinte ao título.
    """
    lines = block["lines"]
    base = max((s for _, s, _, _ in lines), default=0)
    cut = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        txt, size = lines[i][0], lines[i][1]
        if (base and 0 < size <= base * 0.72) or \
                (len(lines) - i <= 4 and _CIT_RE.search(txt)):
            cut = i
        else:
            break
    corpo, cit = lines[:cut], lines[cut:]
    paras, cur, min_left = [], [], None
    for txt, _size, left, _col in corpo:
        if min_left is None or left < min_left:
            min_left = left
        if cur and left > min_left + 25:
            paras.append(cur)
            cur = []
        cur.append(txt)
    if cur:
        paras.append(cur)
    conteudo = "\n\n".join(
        re.sub(r"\s+", " ", " ".join(p)).strip() for p in paras).strip()
    citacao = re.sub(r"\s+", " ", " ".join(t for t, *_ in cit)).strip()
    imagem = len(conteudo) < 80 and any(
        t0 >= block["top"] - 5 for t0, _h in images.get(block["pno"], ()))
    if not imagem and len(conteudo) < 10:
        return None
    return {"ref": block["ref"], "conteudo": conteudo, "citacao": citacao,
            "imagem": imagem}


class _TextoCollector:
    """Coleta blocos 'Texto <ref>' no stream de linhas de uma prova.

    ``feed(txt, size, left, col, pno, top, close)`` retorna True quando a
    linha foi consumida pelo texto-base. ``close='hard'`` fecha o bloco e a
    linha segue o fluxo normal (item novo, comando, cabeçalho, outro Texto).
    """

    def __init__(self, images):
        self.images = images
        self.aberto = None
        self.ultimo = None
        self.por_ref = {}

    def fechar(self):
        if self.aberto is not None:
            t = _finish_texto(self.aberto, self.images)
            if t is not None:
                self.ultimo = t
                if t["ref"]:
                    self.por_ref[t["ref"]] = t
        self.aberto = None

    def abrir(self, ref, pno, top):
        self.fechar()
        self.aberto = {"ref": ref, "lines": [], "pno": pno, "top": top}

    def reset_secao(self):
        """Cabeçalho de seção (CONHECIMENTOS…) desvincula o texto anterior."""
        self.ultimo = None

    def resolver_pendente(self, pend):
        """Bloco solto entre itens → texto-base, remissão ou desvínculo.

        ``pend``: [(txt, size, left, col, pno, top)] — linhas dropadas entre
        um item e o próximo (comandos, intros de figura, texto sem rótulo).
        O bloco é julgado inteiro porque comandos multi-linha remetem ao
        material-base numa linha e comandam noutra. Sem remissão a
        texto/figura o item novo não herda o texto anterior; com remissão
        e prosa o bloco vira um texto sem rótulo (ref=""), e intro de
        figura vira stub ``imagem`` quando não há prosa própria.
        """
        if not pend:
            return
        joined = " ".join(t for t, *_ in pend)
        if not _BASE_REF_RE.search(joined):
            self.reset_secao()
            return
        m = _ENUN_REF_RE.search(joined)
        if m and (t := self.por_ref.get(m.group(1).upper())):
            self.ultimo = t
            return  # 'no texto CB1A1-I' remete ao já coletado
        def _body(ls):
            return [(t, s, l, c) for t, s, l, c, _p, _t in ls
                    if _texto_head(t) is None
                    and not _LIVRE_RE.fullmatch(t.strip())
                    and not _SEP_RE.match(t)]

        body = _body(pend)
        while body and _CMD_TAIL_RE.search(body[-1][0]):
            body.pop()
        stub = False
        if not body:
            if _BASE_IMG_RE.search(joined):
                body, stub = _body(pend), True
            else:
                return  # comando remetendo ao texto corrente — link segue
        block = {"ref": (m.group(1).upper() if m else ""), "lines": body,
                 "pno": pend[0][4], "top": pend[0][5]}
        t = _finish_texto(block, self.images)
        if t is None:
            return
        if _BASE_IMG_RE.search(joined) and (
                stub or any(pend[0][4] <= p <= pend[-1][4]
                            for p in self.images)):
            t["imagem"] = True
        self.ultimo = t
        if t["ref"]:
            self.por_ref[t["ref"]] = t

    def ref_do(self, enunciado):
        """Texto do item: rótulo nomeado > 'o texto' genérico > None.

        Sem remissão no enunciado não se assume posição — questões
        autossuficientes depois de um bloco de texto não herdam o link.
        """
        m = _ENUN_REF_RE.search(enunciado)
        if m and (t := self.por_ref.get(m.group(1).upper())):
            return t
        if _REF_GENERICO_RE.search(enunciado):
            return self.ultimo
        return None


def parse_prova(pdf_path, tipo="ce", variant="modern", audit=False):
    """Ponto de entrada do adapter: {numero: {enunciado, alternativas, assunto, texto}}."""
    if tipo == "mc":
        return _parse_mc(str(pdf_path), audit=audit)
    res = _parse_ce(str(pdf_path), variant=variant, audit=audit)
    if audit:
        its, dropped, textos = res
        return {n: {"enunciado": t, "alternativas": ["Certo", "Errado"],
                    "assunto": "", "texto": textos.get(n)}
                for n, t in its.items()}, dropped
    its, _dropped, textos = res
    return {n: {"enunciado": t, "alternativas": ["Certo", "Errado"],
                "assunto": "", "texto": textos.get(n)}
            for n, t in its.items()}


# ---------------------------------------------------------------------------
# certo/errado (items.py)
# ---------------------------------------------------------------------------

def _merged_lines(pdf_path, gate=True):
    """→ (merged, images). merged: [pno, col, top, left, txt, font_size]."""
    out = subprocess.run(
        ["pdftohtml", "-xml", "-i", "-stdout", pdf_path],
        capture_output=True, text=True).stdout
    root = ET.fromstring(out)
    sizes = _font_sizes(root)
    images = _images_by_page(root)
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
            lines.append((pno, col, top, left, txt, sizes.get(t.get("font"), 0)))
    lines.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

    merged = []
    for pno, col, top, left, txt, size in lines:
        if (merged and merged[-1][0] == pno and merged[-1][1] == col
                and abs(merged[-1][2] - top) <= 8):
            merged[-1][4].append((left, txt, size))
        else:
            merged.append([pno, col, top, left, [(left, txt, size)]])
    for m in merged:
        parts = sorted(m[4])
        m[3] = parts[0][0]
        m[4] = html.unescape(" ".join(t for _, t, _ in parts)).strip()
        m.append(max(s for _, _, s in parts))
    return merged, images


def _is_edge(col, left):
    return left < 60 or (col == 1 and left < 475)


_HEADER_RE = re.compile(r"^[A-ZÀ-Þ][A-ZÀ-Þ0-9 ,()\-–—]{7,}$")
_LIVRE_RE = re.compile(r"espa[çc]o\s+livre[.\s]*", re.I)


def _parse_ce(pdf_path, variant="modern", gate=True, audit=False):
    merged, images = _merged_lines(pdf_path, gate=gate)
    if variant == "old":
        items, dropped, item_textos = _ce_old(merged, images)
    else:
        items, dropped, item_textos = _ce_modern(merged, images)
    if audit:
        return items, dropped, item_textos
    return items, [], item_textos


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
    for pno, col, top, left, txt, size in merged:
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
        out.append((pno, col, top, left, txt, size))
    return out


def _ce_modern(merged, images):
    item_re = re.compile(r"^(\d{1,3})(?:\s+(.*)|\s*$)")
    merged = _strip_justificativas(merged)

    # pass 1: candidate item numbers in encounter order
    candidates = []
    for pno, col, top, left, txt, _s in merged:
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
    tc = _TextoCollector(images)
    item_textos = {}
    items = {}
    dropped = []
    pend = []
    cur_num = None
    last_top = None
    for pno, col, top, left, txt, size in merged:
        if not txt:
            continue
        m = item_re.match(txt)
        is_item = m and _is_edge(col, left) and int(m.group(1)) in valid
        if tc.aberto is not None:
            if is_item:
                tc.fechar()
            elif (h := _texto_head(txt)) is not None:
                tc.abrir(h, pno, top)
                dropped.append((pno, col, txt))
                continue
            elif CMD_RE.match(txt) or _HEADER_RE.match(txt):
                tc.fechar()
                dropped.append((pno, col, txt))
                if _HEADER_RE.match(txt):
                    tc.reset_secao()
                continue
            elif _LIVRE_RE.fullmatch(txt.strip()) or _SEP_RE.match(txt):
                continue
            else:
                tc.aberto["lines"].append((txt, size, left, col))
                dropped.append((pno, col, txt))
                continue
        elif cur_num is None and (h := _texto_head(txt)) is not None:
            tc.resolver_pendente(pend)
            pend = []
            tc.abrir(h, pno, top)
            dropped.append((pno, col, txt))
            continue
        if is_item:
            n = int(m.group(1))
            rest = (m.group(2) or "").strip()
            if not rest and items.get(n):
                continue  # answer-grid echo (folha de rascunho etc.)
            cur_num = n
            tc.resolver_pendente(pend)
            pend = []
            item_textos[n] = tc.ultimo
            items[n] = []
            if rest:
                items[n].append(rest)
            last_top = top
            continue
        if cur_num is None:
            pend.append((txt, size, left, col, pno, top))
            dropped.append((pno, col, txt))
            continue
        indented = (58 <= left < 78) if col == 0 else (468 <= left < 496)
        close = (top - last_top) <= 40
        if indented and close:
            items[cur_num].append(txt)
            last_top = top
        else:
            pend.append((txt, size, left, col, pno, top))
            dropped.append((pno, col, txt))
            cur_num = None
    tc.fechar()
    items = {n: re.sub(r"\s+", " ", " ".join(p)).strip()
             for n, p in items.items() if p}
    for n, enun in items.items():
        if t := tc.ref_do(enun):
            item_textos[n] = t
    return items, dropped, item_textos


def _ce_old(merged, images):
    tc = _TextoCollector(images)
    item_textos = {}
    items = {}
    dropped = []
    pend = []
    last_n = 0
    last_top = None
    last_col = 0
    cur_open = False
    for pno, col, top, left, txt, size in merged:
        if not txt:
            continue
        m = re.match(r"^(.*\S)\s+(\d{1,3})$", txt)
        edge = left < 80 or (col == 1 and left < 500)
        is_item = (m and edge and int(m.group(2)) == last_n + 1
                   and len(m.group(1)) > 15)
        if tc.aberto is not None:
            if is_item:
                tc.fechar()
            elif (h := _texto_head(txt)) is not None:
                tc.abrir(h, pno, top)
                dropped.append((last_n, pno, col, txt))
                continue
            elif CMD_RE.match(txt):
                tc.fechar()
                dropped.append((last_n, pno, col, "CMD:" + txt))
                continue
            elif _LIVRE_RE.fullmatch(txt.strip()) or _SEP_RE.match(txt):
                continue
            else:
                tc.aberto["lines"].append((txt, size, left, col))
                dropped.append((last_n, pno, col, txt))
                continue
        elif not cur_open and (h := _texto_head(txt)) is not None:
            tc.resolver_pendente(pend)
            pend = []
            tc.abrir(h, pno, top)
            dropped.append((last_n, pno, col, txt))
            continue
        if is_item:
            n = int(m.group(2))
            last_n = n
            tc.resolver_pendente(pend)
            pend = []
            item_textos[n] = tc.ultimo
            items[n] = [m.group(1).strip()]
            last_top = top
            cur_open = True
            last_col = col
            continue
        if not cur_open:
            pend.append((txt, size, left, col, pno, top))
            dropped.append((last_n, pno, col, txt))
            continue
        indented = left >= (60 if col == 0 else 470)
        close = (top - last_top) < 30 or col != last_col
        if re.match(r"^\d{1,2}$", txt):
            continue  # lone line-number marker from base text
        if CMD_RE.match(txt):
            cur_open = False
            pend.append((txt, size, left, col, pno, top))
            dropped.append((last_n, pno, col, "CMD:" + txt))
            continue
        if indented and close:
            items[last_n].append(txt)
            last_top = top
            last_col = col
        else:
            cur_open = False
            pend.append((txt, size, left, col, pno, top))
            dropped.append((last_n, pno, col, txt))
    tc.fechar()
    items = {n: re.sub(r"\s+", " ", " ".join(p)).strip()
             for n, p in items.items() if p}
    for n, enun in items.items():
        if t := tc.ref_do(enun):
            item_textos[n] = t
    return items, dropped, item_textos


# ---------------------------------------------------------------------------
# múltipla escolha (mc.py)
# ---------------------------------------------------------------------------

def _parse_mc(pdf_path, audit=False):
    out = subprocess.run(["pdftohtml", "-xml", "-i", "-stdout", pdf_path],
                         capture_output=True, text=True).stdout
    root = ET.fromstring(out)
    sizes = _font_sizes(root)
    images = _images_by_page(root)
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
            lines.append((pno, col, top, left, txt,
                          sizes.get(t.get("font"), 0)))
    lines.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

    merged = []
    for pno, col, top, left, txt, size in lines:
        if (merged and merged[-1][0] == pno and merged[-1][1] == col
                and abs(merged[-1][2] - top) <= 8):
            merged[-1][4].append((left, txt, size))
        else:
            merged.append([pno, col, top, left, [(left, txt, size)]])
    for m in merged:
        parts = sorted(m[4])
        m[3] = parts[0][0]
        m[4] = html.unescape(" ".join(t for _, t, _ in parts)).strip()
        m.append(parts)
        m.append(max(s for _, _, s in parts))

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
    pend = []
    tc = _TextoCollector(images)

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

    for pno, col, top, left, txt, parts, size in merged:
        txt = tag_re.sub("", txt).strip()
        if not txt:
            continue
        # 'FimDoTexto' end-of-base-text marker can merge with the next
        # 'Questão N' on the same PDF line — strip it to recover the item.
        if "FimDoTexto" in txt:
            tc.fechar()
        txt = re.sub(r"^FimDoTexto\s*", "", txt)
        if not txt:
            continue
        qm = quest_re.match(txt)
        if qm:
            tc.resolver_pendente(pend)
            pend = []
            tc.fechar()
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
        if tc.aberto is not None:
            if (h := _texto_head(txt)) is not None:
                tc.abrir(h, pno, top)
                dropped.append((pno, col, txt))
            elif header_re.match(txt):
                tc.fechar()
                dropped.append((pno, col, txt))
                pending_hdr.append(txt)
                cur_header = " ".join(pending_hdr)
                tc.reset_secao()
            elif livre_re.fullmatch(txt.lower()) or _SEP_RE.match(txt):
                pass
            else:
                tc.aberto["lines"].append((txt, size, left, col))
                dropped.append((pno, col, txt))
            continue
        if (in_alt or cur is None) and (h := _texto_head(txt)) is not None:
            tc.resolver_pendente(pend)
            pend = []
            tc.abrir(h, pno, top)
            dropped.append((pno, col, txt))
            continue
        if cur is None:
            pend.append((txt, size, left, col, pno, top))
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
                            for lft, _t, _s in parts[1:]))):
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
                tc.reset_secao()
            elif indent(col, left) and 0 <= (top - last_top) < 34:
                items[cur]["alternativas"][cur_alt].append(txt)
                last_top = top
            else:
                pend.append((txt, size, left, col, pno, top))
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
        texto = tc.ref_do(it["enunciado"])
        res[n] = {"enunciado": it["enunciado"], "alternativas": alts,
                  "assunto": it.get("assunto", ""), "texto": texto}
    if audit:
        return res, dropped
    return res
