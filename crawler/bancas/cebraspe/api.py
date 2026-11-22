"""Cliente da API pública da Cebraspe + descoberta de provas (grátis).

Duas superfícies sobre a mesma API:

- **job-driven** (``list_eventos``/``get_evento``/``download`` +
  ``arquivo_kind``/``arquivo_cargos``): o caminho interativo
  ``next``/``files``/``fetch`` — fetch JSON com cache httpx e download de
  PDFs do CDN.
- **manifesto** (``descobrir``/``mapear_evento``): classifica todos os
  arquivos de todos os eventos, pareia prova ↔ gabarito definitivo e
  resolve cargos → ``crawler/manifests/cebraspe.json``.

Classificação: ``classify`` (rigorosa — só "prova" com layout reconhecido)
alimenta o manifesto; ``arquivo_kind`` (permissiva — baixa tudo que não é
claramente outro) alimenta o fetch, que deixa a decisão final para a
curadoria do job.

Uso::

    python -m crawler discover                  # todos os eventos
    python -m crawler discover --evento IBAMA_25 --evento PF_21
    python -m crawler discover --offline        # só o cache local
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from ...models import slugify
from ...shards import SHARD_DIR, iter_records

API = "https://apis.cebraspe.org.br/cebraspe/eventos"
LIST_URL = f"{API}/tipo/concursos"
DETAIL_URL = f"{API}/{{id}}"
CDN = "https://cdn.cebraspe.org.br/concursos"

_CRAWLER = Path(__file__).resolve().parents[2]
MANIFEST = _CRAWLER / "manifests" / "cebraspe.json"
CACHE_DIR = _CRAWLER / ".cache" / "api"
DATASET = SHARD_DIR   # diretório de shards

USER_AGENT = "papiro-crawler/0.1 (+https://olavostauros.github.io/papiro/)"

Fetch = Callable[[str], Any]  # url -> parsed JSON


# ---------------------------------------------------------------------------
# Normalização de texto
# ---------------------------------------------------------------------------

def norm(text: str) -> str:
    """Maiúsculas, sem acentos, pontuação vira espaço, espaços colapsados."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Z0-9]+", " ", t.upper())
    return re.sub(r"\s+", " ", t).strip()


_SMALL = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "na",
          "no", "nas", "nos", "para", "com", "por", "ao", "aos", "à", "às"}
_ROMAN = re.compile(r"^(?=[ivxlc]+$)c{0,3}(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$", re.I)


def titulo(text: str) -> str:
    """Title-case em português: preposições em minúsculas, siglas preservadas."""
    text = re.sub(r"\s+", " ", text or "").strip()
    words = text.split(" ")
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if i > 0 and lw in _SMALL:
            out.append(lw)
        elif _ROMAN.match(w) or (w.isupper() and not text.isupper()):
            out.append(w.upper())  # numeral romano ou sigla num texto misto
        else:
            # preserva hífens/parênteses: capitaliza cada pedaço alfabético
            out.append(re.sub(r"[^\W\d_]+", lambda m: m.group(0).capitalize(), lw, count=1))
    return " ".join(out)


# ---------------------------------------------------------------------------
# Classificação de arquivos
# ---------------------------------------------------------------------------

def stem(nome: str) -> str:
    return re.sub(r"\.[A-Za-z0-9]{2,4}$", "", nome or "").upper()


def classify(arquivo: dict) -> tuple[str, str]:
    """Retorna (tipo, motivo). tipo ∈ {prova, gabarito, ignorado}."""
    nome = arquivo.get("nomeArquivo") or ""
    d = norm(arquivo.get("descricaoArquivo") or "")
    s = stem(nome)
    if not nome.lower().endswith(".pdf"):
        return "ignorado", "não é PDF"
    if "SEM EFEITO" in d:
        return "ignorado", "sem efeito"
    if any(k in d for k in ("LEDOR", "AMPLIADA", "BRAILLE", "TRANSCRICAO")) \
            or re.search(r"_(SUPER|LEDOR|AMPLIADA|BRAILLE)$", s):
        return "ignorado", "versão de atendimento especial"
    if any(k in d for k in ("DISCURSIVA", "DISSERTATIVA", "PADRAO", "ORAL", "DIGITACAO",
                            "REDACAO", "PRATICA", "TAF", "APTIDAO", "RESULTADO", "EDITAL",
                            "PROVA ESCRITA", "RASCUNHO", "CAPA", "ESPELHO", "PECA",
                            "SENTENCA", "PARECER", "TITULOS")):
        return "ignorado", "não é prova objetiva"
    if "GABARITO DEFINITIVO" in d or "GABARITOS DEFINITIVOS" in d \
            or s.startswith(("GAB_DEFINITIVO", "GABARITO_DEFINITIVO")):
        return "gabarito", ""
    if "GABARITO PRELIMINAR" in d and "PROVA OBJETIVA" not in d:
        return "ignorado", "gabarito preliminar"
    if s.startswith(("GAB_", "GABARITO")):
        return "ignorado", "gabarito não definitivo"
    if "PROVA OBJETIVA" in d or "CADERNO DE PROVA" in d:
        return "prova", ""
    if re.fullmatch(r"(MATRIZ_)?\d{3}_?[A-Z0-9_]+_(\d{3}|C[BGE]\d)_0\d", s):
        return "prova", "inferido pelo nome do arquivo"
    return "ignorado", "não reconhecido"


def arquivo_kind(arq: dict) -> str:
    """Classificação permissiva para o fetch: 'gabarito' | 'prova' | 'outro'."""
    nome = arq["nomeArquivo"].upper()
    desc = (arq.get("descricaoArquivo") or "").upper()
    if "DISCURSIVA" in desc or "CAPA" in desc:
        return "outro"
    if nome.startswith("GAB") or "GABARITO" in desc:
        return "gabarito"
    if "RESPOSTA" in desc or nome.startswith("RESP"):
        return "gabarito"
    if nome.startswith(("DISC", "EDIT")) or "EDITAL" in desc:
        return "outro"
    return "prova"


# "CARGO 3", "DISCIPLINA 10", "ÁREA 01" etc -> idArea list
_CARGO_RE = re.compile(r"(?:CARGOS?|DISCIPLINAS?|ÁREAS?)\s*(?:DE\s*)?(\d+)", re.I)


def arquivo_cargos(arq: dict) -> list[str]:
    """Cargo idAreas referenced by this arquivo's descricao."""
    desc = arq.get("descricaoArquivo") or ""
    return _CARGO_RE.findall(desc)


_GAB_PREFIX = re.compile(r"^(GAB(ARITO)?_DEFINITIVO_)(MATRIZ_)?")
_KEY_SUFFIX = re.compile(r"(_COM_JUSTIFICATIVAS?.*|_ATUALIZADO|_\(\d+\)|_MATRIZ|_CARGO_\d+)$")


def name_key(nome: str, tipo: str) -> str:
    """Chave do caderno, comum a prova e gabarito (ex.: ``057_IBAMA_CB1_01``)."""
    s = re.sub(r"\s+", "_", stem(nome))
    if tipo == "gabarito":
        s = _GAB_PREFIX.sub("", s)
    s = re.sub(r"^MATRIZ_", "", s)
    prev = None
    while prev != s:
        prev, s = s, _KEY_SUFFIX.sub("", s)
    return s


_DESC_NOISE = [
    r"\bGABARITO (OFICIAL )?DEFINITIVO\b",
    r"\bGABARITO PRELIMINAR COM JUSTIFICATIVAS?\b",
    r"\bPROVA OBJETIVA\b",
    r"\bATUALIZADO\b",
    r"\bE\b(?= ?$)",
    r"^E\b",
]


def desc_key(descricao: str) -> str:
    d = norm(descricao)
    for pat in _DESC_NOISE:
        d = re.sub(pat, " ", d)
    # "(P1) E" que sobra entre "PROVA OBJETIVA" e "GABARITO PRELIMINAR"
    d = re.sub(r"\bP\d\b", " ", d)
    d = re.sub(r"^\s*(E\s+)+", " ", d)
    d = re.sub(r"\s+", " ", d).strip()
    return d


# ---------------------------------------------------------------------------
# Cargos
# ---------------------------------------------------------------------------

def limpar_cargo(area: str) -> str:
    a = re.sub(r"\s+", " ", area or "").strip()
    a = re.sub(r"^(CARGO|[ÊE]NFASE|ESPECIALIDADE|[ÁA]REA)\s*\d+\s*[:\-–]\s*", "", a, flags=re.I)
    a = re.sub(r"^CARGO\s*(DE|:)\s*", "", a, flags=re.I)
    a = re.split(r"\s+[-–]\s+(Subs[ií]dio|Remunera|C[óo]digo)", a, flags=re.I)[0]
    a = a.strip(" .-–")
    letras = [c for c in a if c.isalpha()]
    quase_maiusculo = letras and sum(c.isupper() for c in letras) / len(letras) > 0.8
    if quase_maiusculo and not a.isupper():
        a = a.upper()   # senão titulo() trataria cada palavra maiúscula como sigla
    return titulo(a) if a.isupper() or a.islower() else a


def cargo_numero(c: dict, i: int) -> int:
    m = re.search(r"\d+", str(c.get("idArea") or ""))
    if m:
        return int(m.group(0))
    m = re.search(r"(CARGO|ENFASE|AREA)\s*(\d+)", norm(c.get("area") or ""))
    return int(m.group(2)) if m else i + 1


_SLUG_STOP = {"de", "da", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos", "a", "o",
              "as", "os", "para", "com", "por", "ao", "aos"}
_ROTULOS = r"(especialidade|[áa]rea(?: de atua[çc][ãa]o)?|[êe]nfase|perfil|emprego|disciplina|tema)"
SLUG_MAX_PALAVRAS = 3
SLUG_MAX_CHARS = 24


def _palavras(texto: str) -> list[str]:
    return [w for w in slugify(texto).split("-") if w and w not in _SLUG_STOP]


def _curto(palavras: list[str], max_palavras: int = SLUG_MAX_PALAVRAS,
           max_chars: int = SLUG_MAX_CHARS) -> str:
    """Até max_palavras palavras / max_chars caracteres, sem quebrar palavra."""
    out: list[str] = []
    for w in palavras[:max_palavras]:
        if out and len("-".join(out + [w])) > max_chars:
            break
        out.append(w)
    return "-".join(out)


def _longo(palavras: list[str]) -> str:
    return _curto(palavras, max_palavras=6, max_chars=48)


def slug_cargo(nome: str) -> tuple[str, str]:
    """Slug curto do cargo e slug de desempate (com o cargo-base).

    "Técnico Legislativo – Especialidade: Policial Legislativo Federal"
        → ("policial-legislativo", "tecnico-policial-legislativo-federal")
    "Especialista em Regulação de Aviação Civil – Área 1"
        → ("especialista-area-1", ...)
    """
    partes = [p.strip() for p in re.split(r"\s+[–—-]\s+", nome) if p.strip()]
    base = partes[0] if partes else nome
    especifico = ""
    for p in reversed(partes[1:]):
        # "Tema 2: Manejo…" / "Área 3" → base + rótulo + número (analista-tema-2)
        mnum = re.match(rf"^{_ROTULOS}\s*(\d+|[ivxlc]+)\b", p, flags=re.I)
        if mnum:
            w = _palavras(base)[:1] + _palavras(mnum.group(0))
            return _curto(w), _longo(_palavras(base) + _palavras(p))
        p2 = re.sub(rf"^{_ROTULOS}\s*:?\s*", "", p, flags=re.I).strip()
        if re.fullmatch(r"sem especialidade", p2, flags=re.I):
            continue
        if re.fullmatch(r"\d+|[ivxlc]+", p2, flags=re.I):  # "Área 1" → base + área-1
            base_w = _palavras(base)[:1] + _palavras(p)
            return _curto(base_w), _longo(_palavras(base) + _palavras(p))
        if p2:
            especifico = p2
            break
    principal = _palavras(especifico) if especifico else _palavras(base)
    desempate = _palavras(base)[:1] + principal if especifico else _palavras(base)
    return _curto(principal), _longo(desempate)


def cargos_do_evento(evento: dict) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for i, c in enumerate(evento.get("eventoCargos") or []):
        n = cargo_numero(c, i)
        nome = limpar_cargo(c.get("area") or "")
        if not nome:
            continue
        curto, desempate = slug_cargo(nome)
        out[n] = {"numero": n, "nome": nome, "id_cargo": curto, "_desempate": desempate}
    # slugs repetidos no mesmo evento → versão com o cargo-base; ainda repetido → nº do cargo
    for rodada in ("desempate", "numero"):
        cont: dict[str, int] = {}
        for c in out.values():
            cont[c["id_cargo"]] = cont.get(c["id_cargo"], 0) + 1
        for c in out.values():
            if cont[c["id_cargo"]] > 1:
                c["id_cargo"] = (c["_desempate"] if rodada == "desempate"
                                 else f"{c['id_cargo']}-{c['numero']}")
    for c in out.values():
        c.pop("_desempate", None)
    return out


def cargos_conhecidos(dataset: Path = DATASET) -> dict[tuple[str, str], str]:
    """(orgao, cargo) → id_cargo já usado no dataset, para não mudar ids existentes."""
    out: dict[tuple[str, str], str] = {}
    for q in iter_records(dataset):
        m = re.match(r"^[a-z0-9]+-\d{4}-([a-z0-9]+)-(.+)-\d{3}$", q.get("id", ""))
        if m:
            out.setdefault((q["orgao"], q["cargo"]), m.group(2))
    return out


def cargos_da_prova(descricao: str, nome: str, cargos: dict[int, dict]) -> tuple[list[dict], str]:
    """Resolve quais cargos um caderno atende. Retorna (cargos, como)."""
    d = norm(descricao)
    if not cargos:
        return [], "evento sem eventoCargos"
    if re.search(r"\bTOD[OA]S (OS|AS) (CARGOS|ENFASES|AREAS|ESPECIALIDADES)\b", d) \
            or "DEMAIS CARGOS" in d:
        return list(cargos.values()), "todos os cargos"
    m = re.search(r"\b(CARGOS?|ENFASES?|AREAS?|ESPECIALIDADES?|EMPREGOS?|DISCIPLINAS?)"
                  r"\s+(?:DE\s+)?((?:\d+\s*(?:,|E|A)?\s*)+)", d)
    if m:
        nums_txt = m.group(2)
        nums = [int(x) for x in re.findall(r"\d+", nums_txt)]
        if re.search(r"\d+\s+A\s+\d+", nums_txt) and len(nums) == 2:
            nums = list(range(nums[0], nums[1] + 1))
        found = [cargos[n] for n in nums if n in cargos]
        if found:
            return found, "número do cargo na descrição"
    # nome do cargo citado na descrição
    hits = [c for c in cargos.values() if norm(c["nome"]) and norm(c["nome"]) in d]
    if len(hits) == 1:
        return hits, "nome do cargo na descrição"
    if len(cargos) == 1:
        return list(cargos.values()), "evento de cargo único"
    # código do caderno: _00N_ → cargo N
    m = re.search(r"_(\d{3})_0\d$", stem(nome))
    if m and int(m.group(1)) in cargos:
        return [cargos[int(m.group(1))]], "código do caderno (_00N_)"
    return [], "cargo não identificado"


def assunto_de(descricao: str, nome: str = "") -> str:
    d = norm(descricao)
    for k, v in (("CONHECIMENTOS BASICOS", "Conhecimentos Básicos"),
                 ("CONHECIMENTOS ESPECIFICOS", "Conhecimentos Específicos"),
                 ("CONHECIMENTOS GERAIS", "Conhecimentos Gerais"),
                 ("CONHECIMENTOS COMPLEMENTARES", "Conhecimentos Complementares")):
        if k in d:
            return v
    # código do caderno: ..._CB1_01 / ...PECB1_00 → básicos; CG → gerais
    s = stem(nome)
    if re.search(r"CB\d_0\d$", s):
        return "Conhecimentos Básicos"
    if re.search(r"CG\d_0\d$", s):
        return "Conhecimentos Gerais"
    return ""


def fase_de(descricao: str) -> str:
    d = norm(descricao)
    if "CURSO DE FORMACAO" in d:
        return "curso_formacao"
    return "objetiva"


# ---------------------------------------------------------------------------
# Órgão
# ---------------------------------------------------------------------------

def prefixo_evento(evento_url: str) -> str:
    """PC_PE_23 → PC_PE; PETROBRAS_23_NM → PETROBRAS; PF_25_ADM → PF."""
    m = re.match(r"^(.*?)_?\d{2}(?:_.*)?$", evento_url or "")
    return (m.group(1) if m and m.group(1) else evento_url).strip("_")


def orgaos_conhecidos(dataset: Path = DATASET) -> dict[str, tuple[str, str]]:
    """prefixo → (orgao, id_orgao) aprendido do dataset existente (fontes CDN)."""
    out: dict[str, tuple[str, str]] = {}
    for q in iter_records(dataset):
        m = re.search(r"/concursos/([^/]+)/", q.get("fonte", ""))
        if not m:
            continue
        pref = prefixo_evento(m.group(1))
        id_orgao = q["id"].split("-")[2] if q["id"].count("-") >= 3 else slugify(pref)
        out.setdefault(pref, (q["orgao"], id_orgao))
    return out


UFS = {
    "AC": "do Acre", "AL": "de Alagoas", "AP": "do Amapá", "AM": "do Amazonas", "BA": "da Bahia",
    "CE": "do Ceará", "DF": "do Distrito Federal", "ES": "do Espírito Santo", "GO": "de Goiás",
    "MA": "do Maranhão", "MT": "de Mato Grosso", "MS": "de Mato Grosso do Sul",
    "MG": "de Minas Gerais", "PA": "do Pará", "PB": "da Paraíba", "PR": "do Paraná",
    "PE": "de Pernambuco", "PI": "do Piauí", "RJ": "do Rio de Janeiro",
    "RN": "do Rio Grande do Norte", "RS": "do Rio Grande do Sul", "RO": "de Rondônia",
    "RR": "de Roraima", "SC": "de Santa Catarina", "SP": "de São Paulo", "SE": "de Sergipe",
    "TO": "do Tocantins",
}
ORGAOS_UF = {
    "PC": "Polícia Civil", "PM": "Polícia Militar", "CBM": "Corpo de Bombeiros Militar",
    "POLC": "Polícia Científica", "PJC": "Polícia Judiciária Civil", "PP": "Polícia Penal",
}


def orgao_por_sigla(pref: str) -> Optional[str]:
    """PC_MG → "Polícia Civil de Minas Gerais"; CBM_MA → "Corpo de Bombeiros Militar do Maranhão"."""
    m = re.fullmatch(r"([A-Z]+)_?([A-Z]{2})", pref or "")
    if m and m.group(1) in ORGAOS_UF and m.group(2) in UFS:
        return f"{ORGAOS_UF[m.group(1)]} {UFS[m.group(2)]}"
    return None


def orgao_de(evento: dict, conhecidos: dict[str, tuple[str, str]]) -> tuple[str, str, str]:
    """(orgao, id_orgao, origem)."""
    url = evento.get("eventoURL") or ""
    pref = prefixo_evento(url)
    if pref in conhecidos:
        o, i = conhecidos[pref]
        return o, i, "dataset"
    por_sigla = orgao_por_sigla(pref)
    if por_sigla:
        return por_sigla, slugify(pref).replace("-", ""), "sigla do evento"
    completo = (evento.get("eventoNomeCompleto") or "").strip()
    if completo and norm(completo) != norm(url):
        nome = re.sub(r"\s*\([^)]*\)\s*", " ", completo)
        nome = re.sub(r"[\s\-–/]+\d{4}\s*$", "", nome)
        nome = re.split(r"\s*[-–/]\s*(?=[A-Z]{2,}$)", nome.strip())[0]
        # "CONCURSO PARA O QUADRO EFETIVO DE PESSOAL DO MINISTÉRIO…" → "MINISTÉRIO…"
        nome = re.sub(r"^CONCURSO\b.*?\b(PESSOAL|CARGOS?|VAGAS?)\s+D[OA]S?\s+", "", nome,
                      flags=re.I)
        return titulo(nome.strip()), slugify(pref).replace("-", ""), "eventoNomeCompleto"
    abrev = re.sub(r"\s*\d{2,4}\b.*$", "", evento.get("eventoNomeAbreviado") or pref)
    return abrev.strip() or pref, slugify(pref).replace("-", ""), "eventoNomeAbreviado"


# ---------------------------------------------------------------------------
# Pareamento
# ---------------------------------------------------------------------------

def _data(a: dict) -> str:
    return a.get("dataArquivoObj") or ""


def cdn_url(evento_url: str, nome: str) -> str:
    return f"{CDN}/{evento_url}/arquivos/{nome}"


def mapear_evento(evento: dict, conhecidos: dict[str, tuple[str, str]] | None = None,
                  cargos_ids: dict[tuple[str, str], str] | None = None) -> dict:
    """Transforma o detalhe de um evento em entradas de manifesto."""
    conhecidos = conhecidos or {}
    ev = evento.get("eventoURL") or ""
    arquivos = evento.get("arquivosGabarito") or []
    # Eventos antigos repetem o mesmo arquivo uma vez por cargo, cada um com sua
    # descrição: agrupa por nome e guarda todas as descrições.
    provas_por_nome: dict[str, dict] = {}
    gabs_por_nome: dict[str, dict] = {}
    nao_mapeados = []
    for a in arquivos:
        tipo, motivo = classify(a)
        if tipo in ("prova", "gabarito"):
            alvo = provas_por_nome if tipo == "prova" else gabs_por_nome
            atual = alvo.get(a["nomeArquivo"])
            if atual is None:
                alvo[a["nomeArquivo"]] = dict(a, _descs=[a.get("descricaoArquivo") or ""])
            else:
                atual["_descs"].append(a.get("descricaoArquivo") or "")
        elif motivo in ("não reconhecido",):
            nao_mapeados.append({"evento": ev, "arquivo": a.get("nomeArquivo"),
                                 "descricao": a.get("descricaoArquivo"), "motivo": motivo})
    provas = list(provas_por_nome.values())
    # gabaritos mais recentes primeiro (vale o último definitivo publicado)
    gabs = sorted(gabs_por_nome.values(), key=_data, reverse=True)
    by_name: dict[str, dict] = {}
    by_desc: dict[str, dict] = {}
    for g in gabs:
        by_name.setdefault(name_key(g["nomeArquivo"], "gabarito"), g)
        for d in g["_descs"]:
            by_desc.setdefault(desc_key(d), g)

    usados: set[str] = set()
    pares: list[tuple[dict, Optional[dict], str]] = []
    for p in sorted(provas, key=_data, reverse=True):
        g = by_name.get(name_key(p["nomeArquivo"], "prova"))
        como = "nome do arquivo"
        if g is None or g["nomeArquivo"] in usados:
            g = None
            for d in p["_descs"]:
                dk = desc_key(d)
                cand = by_desc.get(dk) if dk else None
                if cand is not None and cand["nomeArquivo"] not in usados:
                    g = cand
                    break
            como = "descrição"
        if g is not None and g["nomeArquivo"] in usados:
            g = None
        if g is not None:
            usados.add(g["nomeArquivo"])
        pares.append((p, g, como if g else ""))

    # chave frouxa: ignora MATRIZ, _PAG_N, versão _0N final e separadores
    # (ex.: 540_PMBC_018_MATRIZ ↔ GAB_DEFINITIVO_MATRIZ_540_PMBC018_PAG_2)
    def loose(nome: str, tipo: str) -> str:
        k = name_key(nome, tipo)
        k = re.sub(r"MATRIZ|_PAG_\d+|_0\d$", "", k)
        return re.sub(r"[^A-Z0-9]", "", k)

    sobra_por_chave: dict[str, list[dict]] = {}
    for g in gabs:
        if g["nomeArquivo"] not in usados:
            sobra_por_chave.setdefault(loose(g["nomeArquivo"], "gabarito"), []).append(g)
    for i, (p, g, _) in enumerate(pares):
        if g is not None:
            continue
        cands = [c for c in sobra_por_chave.get(loose(p["nomeArquivo"], "prova"), [])
                 if c["nomeArquivo"] not in usados]
        if len(cands) == 1:
            pares[i] = (p, cands[0], "nome do arquivo (aproximado)")
            usados.add(cands[0]["nomeArquivo"])

    # sobra exatamente uma prova e um gabarito → pareia por eliminação
    sem_gab = [i for i, (_, g, _) in enumerate(pares) if g is None]
    sobra = [g for g in gabs if g["nomeArquivo"] not in usados]
    if len(sem_gab) == 1 and len(sobra) == 1:
        i = sem_gab[0]
        pares[i] = (pares[i][0], sobra[0], "eliminação")
        usados.add(sobra[0]["nomeArquivo"])

    cargos = cargos_do_evento(evento)
    orgao, id_orgao, orgao_origem = orgao_de(evento, conhecidos)
    for c in cargos.values():  # cargo já no dataset → mesmo slug (ids estáveis)
        if (orgao, c["nome"]) in (cargos_ids or {}):
            c["id_cargo"] = cargos_ids[(orgao, c["nome"])]
    entradas = []
    for p, g, como in pares:
        desc = p.get("descricaoArquivo") or ""
        cs, cargo_como = [], "cargo não identificado"
        for d in p["_descs"]:
            found, how = cargos_da_prova(d, p["nomeArquivo"], cargos)
            if found:
                cargo_como = how
                cs.extend(c for c in found if c not in cs)
            elif not cs:
                cargo_como = how
        if g is None:
            nao_mapeados.append({"evento": ev, "arquivo": p["nomeArquivo"], "descricao": desc,
                                 "motivo": "prova sem gabarito definitivo"})
        if not cs:
            nao_mapeados.append({"evento": ev, "arquivo": p["nomeArquivo"], "descricao": desc,
                                 "motivo": cargo_como})
        entradas.append({
            "evento": ev,
            "id_evento": evento.get("idEvento"),
            "evento_nome": evento.get("eventoNomeAbreviado"),
            "orgao": orgao,
            "id_orgao": id_orgao,
            "orgao_origem": orgao_origem,
            "ano": evento.get("eventoAno"),
            "caderno": name_key(p["nomeArquivo"], "prova"),
            "descricao": re.sub(r"\s+", " ", desc).strip(),
            "fase": fase_de(desc),
            "assunto": assunto_de(desc, p["nomeArquivo"]),
            "cargos": cs,
            "cargo_como": cargo_como,
            "url_prova": cdn_url(ev, p["nomeArquivo"]),
            "url_gabarito": cdn_url(ev, g["nomeArquivo"]) if g else None,
            "pareamento": como or None,
        })
    for g in gabs:
        if g["nomeArquivo"] not in usados:
            nao_mapeados.append({"evento": ev, "arquivo": g["nomeArquivo"],
                                 "descricao": g.get("descricaoArquivo"),
                                 "motivo": "gabarito definitivo sem prova"})
    return {"provas": entradas, "nao_mapeados": nao_mapeados}


# ---------------------------------------------------------------------------
# Rede (httpx) com cache local
# ---------------------------------------------------------------------------

def make_fetch(cache_dir: Path = CACHE_DIR, offline: bool = False,
               refresh: bool = False) -> Fetch:
    cache_dir.mkdir(parents=True, exist_ok=True)
    client = None

    def fetch(url: str) -> Any:
        nonlocal client
        key = re.sub(r"[^A-Za-z0-9_.-]+", "_", url.removeprefix(API).strip("/")) or "root"
        path = cache_dir / f"{key}.json"
        if path.exists() and not refresh:
            return json.loads(path.read_text(encoding="utf-8"))
        if offline:
            raise FileNotFoundError(f"sem cache para {url} (--offline)")
        import httpx
        if client is None:
            client = httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT},
                                  follow_redirects=True)
        r = client.get(url)
        r.raise_for_status()
        data = r.json()
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    return fetch


_default_fetch: Optional[Fetch] = None


def default_fetch() -> Fetch:
    """Fetch compartilhado com cache — usado pelos comandos job-driven."""
    global _default_fetch
    if _default_fetch is None:
        _default_fetch = make_fetch()
    return _default_fetch


def listar_eventos(fetch: Fetch) -> list[dict]:
    grupos = fetch(LIST_URL)
    eventos = []
    for g in grupos:
        for e in g.get("eventos") or []:
            e = dict(e)
            e["_fase"] = g.get("faseEvento")
            eventos.append(e)
    return eventos


def list_eventos(fetch: Optional[Fetch] = None) -> list[dict]:
    """Lista chata de eventos (todas as fases), com cache httpx."""
    return listar_eventos(fetch or default_fetch())


def get_evento(ref, fetch: Optional[Fetch] = None) -> dict:
    """Detalhe por eventoURL slug (id numérico resolve para o slug antes)."""
    fetch = fetch or default_fetch()
    if str(ref).isdigit():
        ref = next(e["eventoURL"] for e in listar_eventos(fetch)
                   if e["idEvento"] == int(ref))
    return fetch(DETAIL_URL.format(id=ref))


def download(evento_url: str, nome_arquivo: str, dest: Path) -> Path:
    """PDF binário do CDN (urllib — fetch cacheia só JSON)."""
    nome = urllib.parse.quote(nome_arquivo)
    req = urllib.request.Request(cdn_url(evento_url, nome),
                                 headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def descobrir(fetch: Fetch, *, eventos_filtro: Iterable[str] = (),
              conhecidos: dict[str, tuple[str, str]] | None = None,
              cargos_ids: dict[tuple[str, str], str] | None = None,
              workers: int = 4, log=print) -> dict:
    lista = listar_eventos(fetch)
    filtro = {e.upper() for e in eventos_filtro}
    if filtro:
        lista = [e for e in lista if (e.get("eventoURL") or "").upper() in filtro]
    conhecidos = orgaos_conhecidos() if conhecidos is None else conhecidos
    cargos_ids = cargos_conhecidos() if cargos_ids is None else cargos_ids

    def detalhe(e: dict):
        try:
            return e, fetch(f"{API}/{e['eventoURL']}"), None
        except Exception as exc:  # noqa: BLE001 — registra e segue
            return e, None, f"{type(exc).__name__}: {exc}"

    provas, nao_mapeados, falhas, sem_provas = [], [], [], []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for i, (e, det, err) in enumerate(pool.map(detalhe, lista), 1):
            if i % 50 == 0:
                log(f"  … {i}/{len(lista)} eventos")
            if err:
                falhas.append({"evento": e.get("eventoURL"), "erro": err})
                continue
            m = mapear_evento(det, conhecidos, cargos_ids)
            if not m["provas"]:
                sem_provas.append(e.get("eventoURL"))
            provas.extend(m["provas"])
            nao_mapeados.extend(m["nao_mapeados"])

    completas = [p for p in provas if p["url_gabarito"] and p["cargos"]]
    cargos = {(p["evento"], c["numero"]) for p in completas for c in p["cargos"]}
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fonte": LIST_URL,
        "resumo": {
            "eventos_listados": len(lista),
            "eventos_com_provas": len({p["evento"] for p in provas}),
            "eventos_sem_provas": len(sem_provas),
            "eventos_com_falha": len(falhas),
            "provas": len(provas),
            "provas_completas": len(completas),
            "provas_objetivas_completas": sum(p["fase"] == "objetiva" for p in completas),
            "cargos_distintos": len(cargos),
            "nao_mapeados": len(nao_mapeados),
        },
        "provas": provas,
        "nao_mapeados": nao_mapeados,
        "falhas": falhas,
        "eventos_sem_provas": sem_provas,
    }


def salvar(manifesto: dict, path: Path = MANIFEST) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def manifest_main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Descoberta de provas Cebraspe → manifesto")
    ap.add_argument("--evento", action="append", default=[], help="eventoURL (repetível)")
    ap.add_argument("--saida", type=Path, default=MANIFEST)
    ap.add_argument("--offline", action="store_true", help="usa só o cache local")
    ap.add_argument("--refresh", action="store_true", help="ignora o cache local")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)

    fetch = make_fetch(offline=args.offline, refresh=args.refresh)
    man = descobrir(fetch, eventos_filtro=args.evento, workers=args.workers)
    salvar(man, args.saida)
    print(json.dumps(man["resumo"], ensure_ascii=False, indent=2))
    print(f"manifesto: {args.saida}")
    return 0
