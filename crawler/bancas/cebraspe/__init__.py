"""Adapter Cebraspe — implementa ``crawler.bancas.base.BancaAdapter``.

API/CDN: ``api.py`` (httpx c/ cache + urllib p/ binários). Parser
autoritativo: ``prova.py`` (``pdftohtml -xml`` por coordenadas). Motor
secundário p/ cruzamento: ``textparse.py`` (``pdftotext -layout``).
Seleção: ``selecao.py``.

Shards = ``<eventoURL>.json``; ids ``cebraspe-<ano>-<id_orgao>-<id_cargo>-NNN``.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from ... import gabarito as gabmod
from ...gabarito import Gabarito, parse_pdf as _parse_gab
from . import api, prova, selecao, textparse


def _slug(s: str) -> str:
    a = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", a.lower())).strip("-")


def _key_for(nome: str) -> str:
    """Short local key from a CDN filename: 106_PF_CB1_01.pdf -> CB1,
    GAB_DEFINITIVO_378_ABIN_015_07.PDF -> 015_07, hash.pdf -> hash[:12]."""
    b = re.sub(r"\.pdf$", "", Path(nome).name, flags=re.I)
    b = re.sub(r"^(GAB(_DEFINITIVO)?_|MATRIZ_|ED_PROVA_|RESPOSTA_DEFINITIVA_)", "",
               b, flags=re.I)
    b = re.sub(r"_PAG_\d+$|_ADAPTADA$|_RESPOSTA.*$", "", b, flags=re.I)
    parts = b.split("_")
    # drop leading numeric seq and event-name parts
    while parts and (parts[0].isdigit() or parts[0].upper()
                     in {"PF", "PRF", "IBAMA", "ABIN", "BANRISUL"}):
        parts.pop(0)
    b = "_".join(parts) or b
    return re.sub(r"[^A-Za-z0-9_]", "_", b)[:24] or "f"


class Cebraspe:
    name = "cebraspe"
    dataset_banca = "Cebraspe"            # rótulo `banca` nos registros
    MANIFEST = api.MANIFEST

    # -- descoberta ------------------------------------------------------
    list_eventos = staticmethod(api.list_eventos)
    get_evento = staticmethod(api.get_evento)
    arquivo_kind = staticmethod(api.arquivo_kind)
    arquivo_cargos = staticmethod(api.arquivo_cargos)
    classify = staticmethod(api.classify)
    norm = staticmethod(api.norm)

    # -- download ----------------------------------------------------------
    download = staticmethod(api.download)

    @staticmethod
    def fetch(detalhe: dict, workdir: Path, log=print) -> dict[str, str]:
        """Baixa provas+gabaritos classificados → {nomeArquivo: nome local}."""
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, str] = {}
        for a in detalhe.get("arquivosGabarito") or []:
            kind = api.arquivo_kind(a)
            if kind not in ("prova", "gabarito"):
                continue
            key = _key_for(a["nomeArquivo"])
            local = f"{kind[:3]}_{key}.pdf"
            i = 2
            while local in manifest.values():
                local = f"{kind[:3]}_{key}_{i}.pdf"
                i += 1
            dest = workdir / local
            if not dest.exists():
                api.download(detalhe["eventoURL"], a["nomeArquivo"], dest)
            manifest[a["nomeArquivo"]] = local
            log(f"{kind:8} {local}  <- {a['nomeArquivo']}")
        return manifest

    # -- parsing -----------------------------------------------------------
    @staticmethod
    def parse_prova(pdf: Path, *, tipo: str, variant: str = "modern",
                    audit: bool = False):
        return prova.parse_prova(str(pdf), tipo=tipo, variant=variant,
                                 audit=audit)

    @staticmethod
    def parse_gabarito(pdf: Path) -> Gabarito:
        return _parse_gab(Path(pdf))

    carregar_gabarito = staticmethod(gabmod.carregar)  # url → Gabarito

    # -- cruzamento (motor secundário) --------------------------------------
    itens_pdf = staticmethod(textparse.itens_do_pdf)
    mc_pdf = staticmethod(textparse.questoes_mc_do_pdf)
    ilegiveis = staticmethod(textparse.ilegiveis)
    ilegiveis_mc = staticmethod(textparse.ilegiveis_mc)

    # -- job ---------------------------------------------------------------
    @staticmethod
    def fonte_url(evento: str, arquivo: str) -> str:
        return api.cdn_url(evento, arquivo)

    @staticmethod
    def chave_prova(fonte_ou_nome: str) -> str:
        """Chave do caderno a partir de URL/nome de arquivo — invariante a
        revisões do arquivo (``_OK``/``_atualizado``) no CDN."""
        return api.name_key(Path(str(fonte_ou_nome)).name, "prova")

    @staticmethod
    def draft_job(detalhe: dict, manifest: dict[str, str], workdir: Path) -> dict:
        """Rascunho de job.json: pareia prova↔gabarito por cargos declarados
        na descrição dos arquivos; sobras caem em ``unmatched``."""
        det = detalhe
        evento = det["eventoURL"]
        arqs = [a for a in det.get("arquivosGabarito") or []
                if api.arquivo_kind(a) in ("prova", "gabarito")]
        por_numero = api.cargos_do_evento(det)
        conhecidos = api.cargos_conhecidos()
        orgao_n = api.norm(det.get("eventoNomeCompleto") or det["eventoNomeAbreviado"])
        cargos = []
        for i, c in enumerate(det.get("eventoCargos") or []):
            info = por_numero.get(api.cargo_numero(c, i), {})
            nome = info.get("nome") or re.sub(
                r"^CARGO\s*\d+\s*[:-]?\s*", "", c["area"]).strip()
            # cargo já no dataset → mesmo id_cargo (ids estáveis)
            idc = conhecidos.get((orgao_n, api.norm(nome)))
            cargos.append({"idArea": c["idArea"], "cargo": nome,
                           "id_cargo": idc or info.get("id_cargo")
                           or _slug(nome)[:40],
                           "provas": []})
        provas = {a["nomeArquivo"]: a for a in arqs if api.arquivo_kind(a) == "prova"}
        gabs = {a["nomeArquivo"]: a for a in arqs if api.arquivo_kind(a) == "gabarito"}
        unmatched = []
        for nome, a in provas.items():
            cids = api.arquivo_cargos(a)
            entry = {"key": _key_for(nome), "prova": manifest[nome],
                     "gabarito": "", "tipo": "ce", "arquivo": nome}
            for gnome, g in gabs.items():
                if api.arquivo_cargos(g) == cids:
                    entry["gabarito"] = manifest[gnome]
            targets = [c for c in cargos if c["idArea"].lstrip("0") in
                       {x.lstrip("0") for x in cids}]
            if targets:
                for t in targets:
                    t["provas"].append(dict(entry))
            else:
                unmatched.append(entry)
        return {"banca": "cebraspe", "evento": evento, "workdir": str(workdir),
                "meta": {"banca": "Cebraspe",
                         "orgao": det["eventoNomeCompleto"] or det["eventoNomeAbreviado"],
                         "ano": det["eventoAno"],
                         "id_orgao": _slug(evento.split("_")[0])},
                "cargos": cargos, "unmatched": unmatched,
                "variant": "modern", "skip": {}, "patch": {}}

    # -- seleção -------------------------------------------------------------
    PRIORIDADES = selecao.PRIORIDADES
    ranquear = staticmethod(selecao.ranquear)
    categoria_de = staticmethod(selecao.categoria_de)
    tipo_caderno = staticmethod(selecao.tipo_caderno)
    parse_anos = staticmethod(selecao.parse_anos)

    # -- manifesto -------------------------------------------------------------
    @staticmethod
    def regen_manifest(path: Path = MANIFEST) -> dict:
        man = api.descobrir(api.make_fetch())
        api.salvar(man, Path(path))
        return man


adapter = Cebraspe()
