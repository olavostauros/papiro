"""Adapter FCC — implementa ``crawler.bancas.base.BancaAdapter``.

Fonte: ``concursosfcc.com.br/concursos/<slug>/provas/index.html`` — página
estática por concurso com blocos por cargo: ``<b>Nome do Cargo</b>`` seguido
de pares Manhã/Tarde de ``Prova-<COD>-Tipo-00N.pdf`` e
``Gabarito_<bloco>_tipo_<N>_Folha_<1|2>.pdf`` (Folha 1 = manhã, 2 = tarde).

Tipos de prova > 1 são as mesmas questões embaralhadas — só o Tipo 1 é
ingerido. Gabaritos são folhas ``NNN - Letra`` materializadas em
``gab_<key>.txt`` (formato Item/Gabarito de ``crawler.gabarito``).

Parser de prova: ``mcxml.parse_mc`` com config ``mcxml.FCC`` — provas FCC
antigas vêm com flag "no copy"; ``mcxml`` decripta com qpdf quando preciso.
Evento/shard: ``FCC_<SLUG>`` (ex.: ``FCC_BCENT105``).
"""

from __future__ import annotations

import html as _html
import re
import unicodedata
from pathlib import Path

from ..gabarito import Gabarito, parse_pdf as _parse_gab
from ..pdf import USER_AGENT, baixar, pdf_to_text
from . import mcxml

BASE = "https://www.concursosfcc.com.br"
_ANO = re.compile(r"(\d)(\d{2})$")
_PROVA_RE = re.compile(r"Prova-([A-Za-z0-9]+)-Tipo-(\d+)", re.I)
_GAB_RE = re.compile(r"Gabarito_(\d+)_tipo_(\d+)_Folha_(\d+)", re.I)
_HREF_RE = re.compile(r'href\s*=\s*"([^"]+)"', re.I)
_CARGO_RE = re.compile(r'color\s*=\s*"?red"?[^>]*>\s*(?:<br\s*/?>)+\s*'
                       r"<b>([^<]+)</b>", re.I)


def _slug(s: str) -> str:
    a = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", a.lower())).strip("-")


def _norm_slug(ref) -> str:
    """``FCC_bcent105``, ``bcent105`` ou URL completa → ``bcent105``."""
    s = str(ref).strip().rstrip("/")
    if "/concursos/" in s:
        s = s.split("/concursos/", 1)[1].split("/")[0]
    return re.sub(r"(?i)^fcc[_-]?", "", s)


def _evento_url(slug: str) -> str:
    return f"FCC_{slug.upper()}"


def _get(url: str) -> str:
    import httpx
    r = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=60,
                  follow_redirects=True)
    r.raise_for_status()
    return r.content.decode("latin-1")


def _prova_key(cod: str, turno: str, tipo: int) -> str:
    return f"{cod}_{turno[0].upper()}T{tipo}"


def list_eventos() -> list[dict]:
    """Concursos listados na página corrente — slugs antigos funcionam
    direto em ``files``/``fetch`` mesmo fora da lista."""
    out = []
    for m in _HREF_RE.finditer(_get(f"{BASE}/concursos/index.html")):
        mm = re.match(r"(?:https?://[^/]+)?/concursos/([a-z0-9]+)/index\.html",
                      m.group(1))
        if not mm:
            continue
        slug = mm.group(1)
        ano = 2000 + int(a.group(2)) if (a := _ANO.search(slug)) else 0
        out.append({"idEvento": slug, "eventoURL": _evento_url(slug),
                    "eventoNomeAbreviado": slug, "eventoNomeCompleto": "",
                    "eventoAno": ano, "eventoTotalVagas": 0,
                    "eventoCargos": []})
    return out


def get_evento(ref) -> dict:
    """Parseia ``/concursos/<slug>/provas/index.html`` → detalhe no formato
    Cebraspe (``eventoCargos`` + ``arquivosGabarito``)."""
    slug = _norm_slug(ref)
    url = f"{BASE}/concursos/{slug}/provas/index.html"
    page = _get(url)
    title = re.search(r"<title>([^<]+)", page, re.I)
    orgao = _html.unescape(title.group(1)).strip() if title else slug

    # percorre na ordem do documento: cabeçalhos de cargo e links
    marcas = sorted(
        [(m.start(), ("cargo", m)) for m in _CARGO_RE.finditer(page)]
        + [(m.start(), ("href", m)) for m in _HREF_RE.finditer(page)])
    cargos: list[dict] = []          # {"idArea": cod, "area": nome}
    arquivos: list[dict] = []
    cur_bloco = 0
    for _pos, (what, m) in marcas:
        if what == "cargo":
            nome = _html.unescape(m.group(1)).strip().rstrip("\n")
            nome = re.sub(r"\s+", " ", nome)
            cur_bloco += 1
            cod = f"B{cur_bloco}"     # refinado quando a prova traz o código
            cargos.append({"idArea": cod, "area": nome, "_bloco": cur_bloco})
            continue
        href = m.group(1)
        base = Path(href).name
        if pm := _PROVA_RE.search(base):
            turno = "manha" if "/manha/" in href else \
                    "tarde" if "/tarde/" in href else ""
            arquivos.append({"nomeArquivo": href, "descricaoArquivo":
                             f"Prova Tipo {pm.group(2)} {turno}".strip(),
                             "_kind": "prova", "_cod": pm.group(1).upper(),
                             "_tipo": int(pm.group(2)), "_turno": turno,
                             "_bloco": cur_bloco})
        elif gm := _GAB_RE.search(base):
            arquivos.append({"nomeArquivo": href, "descricaoArquivo":
                             f"Gabarito tipo {gm.group(2)} folha {gm.group(3)}",
                             "_kind": "gabarito", "_bloco": int(gm.group(1)),
                             "_tipo": int(gm.group(2)),
                             "_folha": int(gm.group(3))})
    # o código do cargo vem do nome da prova (ANA1 → bloco 1, ANA2 → bloco 2…)
    por_bloco = {c["_bloco"]: c for c in cargos}
    for a in arquivos:
        if a["_kind"] == "prova" and a["_bloco"] in por_bloco:
            por_bloco[a["_bloco"]]["idArea"] = a["_cod"]
    for c in cargos:
        c.pop("_bloco", None)
    ano = 2000 + int(a.group(2)) if (a := _ANO.search(slug)) else 0
    return {"eventoURL": _evento_url(slug), "idEvento": slug,
            "eventoNomeAbreviado": slug,
            "eventoNomeCompleto": re.sub(r"(?i)\s*-\s*FCC.*$", "", orgao),
            "eventoAno": ano, "eventoTotalVagas": 0,
            "eventoCargos": cargos, "arquivosGabarito": arquivos,
            "_page": url}


def arquivo_kind(arq: dict) -> str:
    return arq.get("_kind") or "outro"


def arquivo_cargos(arq: dict) -> list[str]:
    return [arq["_cod"]] if arq.get("_cod") else []


def _gab_txt(pdf: Path, dest: Path) -> None:
    """Folha ``NNN - Letra`` → ``gab_*.txt`` no formato Item/Gabarito."""
    respostas = {}
    for n, r in re.findall(r"(\d{1,3})\s*[-–—]\s*([A-EXx]|ANUL\w*)",
                           pdf_to_text(Path(pdf))):
        respostas[int(n)] = "X" if r.upper().startswith(("X", "ANUL")) \
            else r.upper()
    if not respostas:
        raise ValueError(f"gabarito sem pares item-letra: {pdf}")
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
    """Baixa provas+gabaritos **tipo 1** (outros tipos = mesmas questões)
    e materializa os gabaritos em ``gab_<key>.txt``."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    bloco_cod = {i + 1: c["idArea"] for i, c in
                 enumerate(detalhe.get("eventoCargos") or [])}
    manifest: dict[str, str] = {}
    for a in detalhe.get("arquivosGabarito") or []:
        if a.get("_kind") != "prova" or a["_tipo"] != 1:
            continue
        cod = a.get("_cod") or bloco_cod.get(a["_bloco"], "X")
        key = _prova_key(cod, a["_turno"] or "M", a["_tipo"])
        local = f"pro_{key}.pdf"
        dest = workdir / local
        if not dest.exists():
            download(detalhe["eventoURL"], a["nomeArquivo"], dest)
        manifest[a["nomeArquivo"]] = local
        a["_key"] = key
        log(f"prova     {local}  <- {a['nomeArquivo']}")
    for a in detalhe.get("arquivosGabarito") or []:
        if a.get("_kind") != "gabarito" or a["_tipo"] != 1:
            continue
        cod = bloco_cod.get(a["_bloco"])
        if not cod:
            log(f"!! gabarito sem bloco resolvido: {a['nomeArquivo']}")
            continue
        turno = "M" if a["_folha"] == 1 else "T"
        key = _prova_key(cod, turno, a["_tipo"])
        pdf = workdir / f"raw_{key}.pdf"
        if not pdf.exists():
            download(detalhe["eventoURL"], a["nomeArquivo"], pdf)
        local = f"gab_{key}.txt"
        _gab_txt(pdf, workdir / local)
        manifest[a["nomeArquivo"]] = local
        a["_key"] = key
        log(f"gabarito  {local}  <- {a['nomeArquivo']}")
    return manifest


def parse_prova(pdf: Path, *, tipo: str, variant: str = "modern",
                audit: bool = False):
    return mcxml.parse_mc(str(pdf), audit=audit, **mcxml.FCC)


def parse_gabarito(pdf: Path) -> Gabarito:
    return _parse_gab(Path(pdf))


def fonte_url(evento: str, arquivo: str) -> str:
    return arquivo if arquivo.startswith("http") else BASE + arquivo


def draft_job(detalhe: dict, manifest: dict[str, str], workdir: Path) -> dict:
    """Pareia prova tipo 1 ↔ folha materializada pela chave ``<COD>_<turno>T1``."""
    evento = detalhe["eventoURL"]
    gabs = {a.get("_key"): a for a in detalhe.get("arquivosGabarito") or []
            if a.get("_kind") == "gabarito" and a.get("_key")}
    cargos = []
    for c in detalhe.get("eventoCargos") or []:
        nome = c["area"]
        cargos.append({"idArea": c["idArea"], "cargo": nome,
                       "id_cargo": _slug(nome)[:40], "provas": []})
    unmatched = []
    for a in detalhe.get("arquivosGabarito") or []:
        if a.get("_kind") != "prova" or a["_tipo"] != 1 or not a.get("_key"):
            continue
        g = gabs.get(a["_key"])
        entry = {"key": a["_key"], "prova": manifest[a["nomeArquivo"]],
                 "gabarito": manifest[g["nomeArquivo"]] if g else "",
                 "tipo": "mc", "arquivo": a["nomeArquivo"]}
        targets = [c for c in cargos if c["idArea"] == a.get("_cod")]
        if targets:
            for t in targets:
                t["provas"].append(dict(entry))
        else:
            unmatched.append(entry)
    return {"banca": "fcc", "evento": evento, "workdir": str(workdir),
            "meta": {"banca": "FCC",
                     "orgao": detalhe["eventoNomeCompleto"] or evento,
                     "ano": detalhe["eventoAno"],
                     "id_orgao": re.sub(r"\d+$", "", _norm_slug(evento))},
            "cargos": cargos, "unmatched": unmatched,
            "variant": "modern", "skip": {}, "patch": {}}


adapter = type("Fcc", (), {
    "name": "fcc",
    "dataset_banca": "FCC",
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
