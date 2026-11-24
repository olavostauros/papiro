"""Adapter FGV — implementa ``crawler.bancas.base.BancaAdapter``.

Fonte: ``conhecimento.fgv.br/concursos/<slug>`` — página Drupal estática do
concurso com todos os PDFs linkados. Provas nomeiam-se
``<cod>-<cargo-slug>-<codprova>-tipo-<N>.pdf`` (ou ``<cargo>-<code>-tipo-N``);
tipos > 1 são as mesmas questões embaralhadas — só o Tipo 1 é ingerido.

Gabaritos (``*gabarito*``/``gabdef*``) são PDFs com seções por cargo —
``Auditor Fiscal - 1 - Turno Manhã`` / ``ANALISTA … – PROVA TIPO 1`` —
seguidas de linhas número→letra (``*`` = anulada). O ``fetch`` fatia as
seções e materializa ``gab_<key>.txt`` no formato Item/Gabarito de
``crawler.gabarito``.

Parser de prova: ``mcxml.parse_mc`` com config ``mcxml.FGV``.
Evento/shard: ``FGV_<SLUG>`` (ex.: ``FGV_RFB22``).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from ..gabarito import Gabarito, parse_pdf as _parse_gab
from ..pdf import USER_AGENT, baixar, pdf_to_text
from . import mcxml

BASE = "https://conhecimento.fgv.br"
_PROVA_RE = re.compile(r"-tipo-(\d+)\.pdf$", re.I)
_GAB_RE = re.compile(r"gabarito|gabdef|^gab[-_]", re.I)
_SLUG_RE = re.compile(r"(?i)^fgv[_-]?")


def _slug(s: str) -> str:
    a = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", a.lower())).strip("-")


def _norm_slug(ref) -> str:
    s = str(ref).strip().rstrip("/")
    if "/concursos/" in s:
        s = s.split("/concursos/", 1)[1].split("/")[0]
    return _SLUG_RE.sub("", s)


def _evento_url(slug: str) -> str:
    return f"FGV_{slug.upper()}"


def _get(url: str) -> str:
    import httpx
    r = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=60,
                  follow_redirects=True)
    r.raise_for_status()
    return r.text


def _cargo_da_prova(nome: str) -> str:
    """``cns101-auditor-fiscal-…-afrfbcns101-tipo-1.pdf`` →
    ``auditor-fiscal-da-receita-federal-do-brasil``;
    ``analista-tributario-rfb200-tipo-1.pdf`` → ``analista-tributario``;
    ``auditor-fiscalfrb100-tipo-1.pdf`` (código colado) → ``auditor-fiscal``."""
    b = re.sub(r"\.pdf$", "", Path(nome).name, flags=re.I)
    b = re.sub(r"-tipo-\d+$", "", b)
    b = re.sub(r"^cns\d+-", "", b)              # prefixo de caderno
    b = re.sub(r"-[a-z]*cns\d+$", "", b)        # -afrfbcns101, -atrfbcns201
    b = re.sub(r"-[a-z]{2,6}\d+$", "", b)       # -frb100, -rfb200
    b = re.sub(r"[a-z]{3}\d{3}$", "", b)        # colado: fiscalfrb100 → fiscal
    return b.rstrip("-_")


def _key_for(nome: str) -> str:
    b = _cargo_da_prova(nome)
    m = re.search(r"tipo-(\d+)", nome, re.I)
    cns = re.search(r"cns(\d+)", nome, re.I)
    return f"{_slug(b)}_{'c' + cns.group(1) if cns else ''}t{m.group(1) if m else '1'}"


def list_eventos() -> list[dict]:
    out = []
    for m in re.finditer(r'href="(/concursos/([a-z0-9._-]+))"',
                         _get(f"{BASE}/concursos")):
        slug = m.group(2)
        if slug == "nosso-portfolio":
            continue
        out.append({"idEvento": slug, "eventoURL": _evento_url(slug),
                    "eventoNomeAbreviado": slug, "eventoNomeCompleto": "",
                    "eventoAno": 0, "eventoTotalVagas": 0, "eventoCargos": []})
    return out


def get_evento(ref) -> dict:
    """Página do concurso → detalhe no formato Cebraspe."""
    slug = _norm_slug(ref)
    url = f"{BASE}/concursos/{slug}"
    page = _get(url)
    title = re.search(r"<title>([^<]+)", page, re.I)
    orgao = re.sub(r"\s*\|\s*FGV.*$", "", title.group(1)).strip() \
        if title else slug
    ano_m = re.search(r"\b(19|20)\d{2}\b", orgao)
    cargos: dict[str, dict] = {}
    arquivos: list[dict] = []
    for href in re.findall(r'href="([^"]+\.pdf)"', page, re.I):
        if href.startswith("/"):
            href = BASE + href
        nome = Path(href.split("?")[0]).name
        desc = unicodedata.normalize("NFKC", nome)
        if pm := _PROVA_RE.search(nome):
            cod = _cargo_da_prova(nome)
            cargos.setdefault(cod, {"idArea": cod, "area": cod.replace("-", " ")})
            arquivos.append({"nomeArquivo": nome, "descricaoArquivo": desc,
                             "_kind": "prova", "_cod": cod,
                             "_tipo": int(pm.group(1)), "_url": href})
        elif _GAB_RE.search(nome):
            arquivos.append({"nomeArquivo": nome, "descricaoArquivo": desc,
                             "_kind": "gabarito", "_url": href})
        else:
            arquivos.append({"nomeArquivo": nome, "descricaoArquivo": desc,
                             "_kind": "outro", "_url": href})
    return {"eventoURL": _evento_url(slug), "idEvento": slug,
            "eventoNomeAbreviado": slug,
            "eventoNomeCompleto": orgao,
            "eventoAno": int(ano_m.group(0)) if ano_m else 0,
            "eventoTotalVagas": 0,
            "eventoCargos": list(cargos.values()),
            "arquivosGabarito": arquivos, "_page": url}


def arquivo_kind(arq: dict) -> str:
    return arq.get("_kind") or "outro"


def arquivo_cargos(arq: dict) -> list[str]:
    return [arq["_cod"]] if arq.get("_cod") else []


# -- gabarito: seções "<cargo> - <tipo> - Turno <turno>" + linhas número/letra
_SEC_RE = re.compile(
    r"^\s*(.+?)\s*[-–—]+\s*(?:(?:PROVA\s+)?TIPO\s*)?(\d+)\s*"
    r"(?:\([^)]*\)|[-–—]\s*Turno.*|)\s*$", re.I)
_NUMS_RE = re.compile(r"^\s*\d{1,3}(?:\s+\d{1,3})+\s*$")
_LETRAS_RE = re.compile(r"^\s*[A-EX*](?:\s+[A-EX*])+\s*$")


def _gab_secoes(pdf: Path) -> dict[str, dict[int, str]]:
    """``{secao: {num: letra}}`` — ``secao`` = ``<cargo-slug>_t<tipo>[_<turno>]``."""
    secoes: dict[str, dict[int, str]] = {}
    cur = None
    pend_nums: list[int] = []
    for ln in pdf_to_text(Path(pdf)).splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if _NUMS_RE.match(ln):
            pend_nums += [int(x) for x in ln.split()]
            continue
        if pend_nums and _LETRAS_RE.match(ln):
            if cur is not None:
                letras = [x.upper() for x in ln.split()]
                for n, r in zip(pend_nums, letras):
                    secoes[cur][n] = "X" if r in ("X", "*") else r
            pend_nums = []
            continue
        pend_nums = []
        m = _SEC_RE.match(ln)
        if m:
            cargo = _slug(re.sub(r"\s*\([A-Z]+\)\s*$", "", m.group(1)))
            turno = "m" if re.search(r"(?i)manh", ln) else \
                    "t" if re.search(r"(?i)tarde", ln) else ""
            key = f"{cargo}_t{m.group(2)}{turno}"
            cur = key
            secoes.setdefault(key, {})
    return secoes


def _gab_txt(respostas: dict[int, str], dest: Path) -> None:
    nums = sorted(respostas)
    linhas = []
    for i in range(0, len(nums), 20):
        chunk = nums[i:i + 20]
        linhas.append("Item      " + " ".join(str(n) for n in chunk))
        linhas.append("Gabarito  " + " ".join(respostas[n] for n in chunk))
    dest.write_text("\n".join(linhas) + "\n")


def download(evento: str, nome_arquivo: str, dest: Path) -> Path:
    cached = baixar(fonte_url(evento, nome_arquivo))
    Path(dest).write_bytes(cached.read_bytes())
    return dest


def fetch(detalhe: dict, workdir: Path, log=print) -> dict[str, str]:
    """Baixa provas tipo 1 + gabaritos, fatia as seções e materializa
    ``gab_<cargo>_t1<turno>.txt``."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    gab_pdfs: list[tuple[dict, Path]] = []
    for a in detalhe.get("arquivosGabarito") or []:
        if a.get("_kind") == "prova" and a["_tipo"] == 1:
            key = _key_for(a["nomeArquivo"])
            local = f"pro_{key}.pdf"
            dest = workdir / local
            if not dest.exists():
                _baixar_url(a["_url"], dest)
            manifest[a["nomeArquivo"]] = local
            a["_key"] = key
            log(f"prova     {local}  <- {a['nomeArquivo']}")
        elif a.get("_kind") == "gabarito":
            raw = workdir / f"rawgab_{_slug(Path(a['nomeArquivo']).stem)[:40]}.pdf"
            if not raw.exists():
                _baixar_url(a["_url"], raw)
            gab_pdfs.append((a, raw))
            log(f"gabarito  {raw.name}  <- {a['nomeArquivo']}")
    # seções são namespaceadas pelo arquivo — nomes de cargo se repetem
    # entre gabaritos de exames diferentes no mesmo evento.
    secoes: dict[str, dict[int, str]] = {}
    for a, raw in gab_pdfs:
        try:
            tag = _slug(Path(a["nomeArquivo"]).stem)[:36]
            for sec, resp in _gab_secoes(raw).items():
                secoes[f"{tag}__{sec}"] = resp
        except Exception as ex:
            log(f"!! gabarito sem seções: {raw.name}: {ex}")
    secoes = {s: r for s, r in secoes.items() if r}   # títulos espúrios → vazio
    for sec, resp in sorted(secoes.items()):
        local = f"gab_{sec}.txt"
        _gab_txt(resp, workdir / local)
        log(f"gab-txt   {local}  ({len(resp)} itens)")
    detalhe["_gab_secoes"] = sorted(secoes)
    return manifest


def _baixar_url(url: str, dest: Path) -> Path:
    cached = baixar(url)
    Path(dest).write_bytes(cached.read_bytes())
    return dest


def parse_prova(pdf: Path, *, tipo: str, variant: str = "modern",
                audit: bool = False):
    return mcxml.parse_mc(str(pdf), audit=audit, **mcxml.FGV)


def parse_gabarito(pdf: Path) -> Gabarito:
    return _parse_gab(Path(pdf))


def fonte_url(evento: str, arquivo: str) -> str:
    return arquivo if arquivo.startswith("http") \
        else f"{BASE}/sites/default/files/concursos/{arquivo}"


def draft_job(detalhe: dict, manifest: dict[str, str], workdir: Path) -> dict:
    """Cargos de ``_cargo_da_prova``; gabarito pareado por seção materializada
    ``gab_<cargo>_t1<turno>.txt`` — seções sem prova ficam fora do job."""
    evento = detalhe["eventoURL"]
    secoes = detalhe.get("_gab_secoes") or []
    cargos = []
    for c in detalhe.get("eventoCargos") or []:
        cargos.append({"idArea": c["idArea"], "cargo": c["area"],
                       "id_cargo": _slug(c["area"])[:40], "provas": []})
    unmatched = []
    seen_keys: set[str] = set()
    for a in detalhe.get("arquivosGabarito") or []:
        if a.get("_kind") != "prova" or a["_tipo"] != 1 or not a.get("_key"):
            continue
        if a["_key"] in seen_keys:
            continue                        # mesmo caderno linkado 2× (typos de nome)
        seen_keys.add(a["_key"])
        # seções são ``<arquivo>__<cargo>_t<N><turno>``: pareia só se houver
        # exatamente uma candidata ao cargo — ambíguas ficam p/ curadoria.
        cargo_slug = _slug(a["_cod"])
        cands = [s for s in secoes
                 if s.split("__", 1)[-1].startswith(f"{cargo_slug}_t{a['_tipo']}")]
        sec = cands[0] if len(cands) == 1 else ""
        entry = {"key": a["_key"], "prova": manifest[a["nomeArquivo"]],
                 "gabarito": f"gab_{sec}.txt" if sec else "",
                 "tipo": "mc", "arquivo": a["nomeArquivo"]}
        targets = [c for c in cargos if c["idArea"] == a["_cod"]]
        if targets:
            for t in targets:
                t["provas"].append(dict(entry))
        else:
            unmatched.append(entry)
    return {"banca": "fgv", "evento": evento, "workdir": str(workdir),
            "meta": {"banca": "FGV",
                     "orgao": detalhe["eventoNomeCompleto"] or evento,
                     "ano": detalhe["eventoAno"],
                     "id_orgao": _slug(_norm_slug(evento))},
            "cargos": cargos, "unmatched": unmatched,
            "variant": "modern", "skip": {}, "patch": {}}


adapter = type("Fgv", (), {
    "name": "fgv",
    "dataset_banca": "FGV",
    "list_eventos": staticmethod(list_eventos),
    "get_evento": staticmethod(get_evento),
    "arquivo_kind": staticmethod(arquivo_kind),
    "arquivo_cargos": staticmethod(arquivo_cargos),
    "download": staticmethod(download),
    "fetch": staticmethod(fetch),
    "parse_prova": staticmethod(parse_prova),
    "parse_gabarito": staticmethod(parse_gabarito),
    "fonte_url": staticmethod(fonte_url),
    "draft_job": staticmethod(draft_job),
})()
