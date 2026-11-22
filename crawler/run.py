"""Pipeline Cebraspe ponta a ponta (CLI).

manifesto → pula o que já está no dataset → gabarito definitivo (grátis) →
``extract_prova`` (Firecrawl, créditos) → validação → append no dataset.

Exemplos::

    python -m crawler.run --dry-run                       # zero créditos
    python -m crawler.run --dry-run --evento TRF6_24
    python -m crawler.run --limite-provas 1 --teto-creditos 30 --caderno 945_ANAC_23_CB1_01

Controle de gasto:

- ``--teto-creditos N`` é obrigatório fora do ``--dry-run``. Antes de cada
  extração o custo é estimado (páginas do PDF + 4, padrão observado no lote
  PF 2025) e a execução PARA se ``gasto + estimativa > N``.
- O gasto real vem do ledger ``FIRECRAWL_USAGE.md`` (``extract_prova`` já
  registra via ``crawler/usage.py``). Se a resposta não trouxer
  ``creditsUsed`` e nada for registrado, o run registra a estimativa e avisa.
- Toda extração é salva em ``crawler/.cache/extracoes/`` antes de validar:
  re-execuções reaproveitam o JSON e não gastam crédito de novo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import discover, gabarito as gabmod, usage
from .models import ProvaExtraida, ProvaMeta, Questao, QuestaoExtraida, to_questao
from .shards import evento_key, write_shard
from .validate import Relatorio, formatar, validar

HERE = Path(__file__).resolve().parent
DATASET = discover.DATASET
EXTRACOES = HERE / ".cache" / "extracoes"
REPORTS = HERE / "reports"
CUSTO_FIXO = 4  # créditos de json-extraction por prova, além de 1/página

Extractor = Callable[[str, str], ProvaExtraida]          # (url, task) -> prova
GabLoader = Callable[[str], gabmod.Gabarito]             # url -> gabarito
PageCounter = Callable[[str], int]                       # url -> nº de páginas
PdfItens = Callable[[str, list[int]], dict[int, str]]    # url, itens -> texto por item


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

@dataclass
class Dataset:
    path: Path
    questoes: list[dict]
    ids: set[str] = field(default_factory=set)
    fontes: set[str] = field(default_factory=set)
    eventos_pasta: set[str] = field(default_factory=set)  # fonte = só a pasta do evento
    _novos: list[dict] = field(default_factory=list)    # p/ upsert no banco
    _dirty: set[str] = field(default_factory=set)       # eventos a regravar

    @classmethod
    def carregar(cls, path: Path = DATASET) -> "Dataset":
        # path = diretório de shards (padrão) ou um JSON flat legado
        qs = list(discover._iter_records(path))
        ds = cls(path=path, questoes=qs)
        for q in qs:
            ds.ids.add(q["id"])
            f = q.get("fonte", "")
            ds.fontes.add(f.lower())
            m = re.search(r"/concursos/([^/]+)/(?:arquivos/?)?$", f)
            if m:
                ds.eventos_pasta.add(m.group(1).upper())
        return ds

    def ja_ingerida(self, entrada: dict) -> Optional[str]:
        if entrada["url_prova"].lower() in self.fontes:
            return "url da prova já é fonte no dataset"
        if entrada["evento"].upper() in self.eventos_pasta:
            return "evento já ingerido (fonte só com a pasta do evento)"
        return None

    def append(self, novas: list[Questao]) -> tuple[int, list[str]]:
        add, colisoes = 0, []
        for q in novas:
            if q.id in self.ids:
                colisoes.append(q.id)
                continue
            d = q.model_dump()
            self.questoes.append(d)
            self._novos.append(d)
            self._dirty.add(evento_key(q.fonte, d))
            self.ids.add(q.id)
            self.fontes.add(q.fonte.lower())
            add += 1
        return add, colisoes

    def salvar(self) -> None:
        if self.path.is_dir():
            self._salvar_shards()
            return
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(self.questoes, ensure_ascii=False, indent=2))
        tmp.replace(self.path)
        self._novos.clear()

    def _salvar_shards(self) -> None:
        """Regrava só os shards tocados e faz upsert no banco (DATABASE_URL)."""
        by_evento: dict[str, list[dict]] = {}
        for q in self.questoes:
            by_evento.setdefault(evento_key(q["fonte"], q), []).append(q)
        for ev in sorted(self._dirty):
            write_shard(ev, by_evento[ev], shard_dir=self.path)
            print(f"shard {ev}: {len(by_evento[ev])} itens")
        self._dirty.clear()
        if self._novos and os.environ.get("DATABASE_URL"):
            try:
                from .db import get_engine, sync_records
                st = sync_records(self._novos, get_engine())
                print(f"db: +{st.inserted} inseridos ({st.skipped} já existiam)")
            except Exception as exc:
                print(f"!! shards gravados, mas db sync falhou: {exc}",
                      file=sys.stderr)
        self._novos.clear()


# ---------------------------------------------------------------------------
# Seleção
# ---------------------------------------------------------------------------

def tipo_caderno(descricao: str) -> Optional[int]:
    m = re.search(r"\bTIPO (\d+)\b", discover.norm(descricao))
    return int(m.group(1)) if m else None


# Categorias de prioridade, na ordem em que são processadas. Casam com
# norm("<eventoURL> <eventoNomeAbreviado> <órgão>") (maiúsculas, sem acento).
PRIORIDADES: dict[str, str] = {
    "tribunais": r"\bTRIBUNA|\b(TJ|TJDFT|TJM|TRF|TRT|TRE|STJ|STF|STM|TST|TSE|TCU|TCE|TCM|TC|CNJ|"
                 r"CPNUJE)\b|\b(TRF|TRT)\d",
    "policias": r"\bPOLICIA|\bPOLICIAL|\b(PF|PRF|PC|PM|PCDF|PJC|POLC|PP|PPF|DPF|DEPEN|SEAP|SSP|"
                r"CBM|CBMDF)\b|PENITENCI|BOMBEIRO",
    "inss": r"\bINSS\b|SEGURO SOCIAL",
    "bancos": r"\bBANCO\b|\b(BB|BCB|BACEN|CAIXA|CEF|BNB|BASA|BRB|BNDES|BDMG|BANRISUL|BANESE|"
              r"BANPARA)\b",
    # só reguladoras: agências nacionais e estaduais de regulação
    # (sem a sigla ANA solta: "ANA" também abrevia "Analista" nos nomes de evento)
    "agencias": r"AGENCIA NACIONAL|REGULACAO|REGULADORA|AGUAS E SANEAMENTO|"
                r"\b(ANAC|ANATEL|ANEEL|ANP|ANS|ANTAQ|ANTT|ANVISA|ANM|"
                r"ANCINE|ARSAL|ARSESP|ADASA|AGERGS|AGER|AGEPAR|ARCE|ARSAE)\b",
}


def parse_anos(texto: Optional[str]) -> Optional[set[int]]:
    """'2022-2026' → {2022,…,2026}; '2021,2023' → {2021, 2023}."""
    if not texto:
        return None
    anos: set[int] = set()
    for parte in texto.split(","):
        parte = parte.strip()
        m = re.fullmatch(r"(\d{4})\s*-\s*(\d{4})", parte)
        if m:
            anos.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif parte:
            anos.add(int(parte))
    return anos


def categoria_de(e: dict, categorias: Iterable[str]) -> Optional[str]:
    texto = discover.norm(f"{e.get('evento', '')} {e.get('evento_nome') or ''} {e.get('orgao', '')}")
    for c in categorias:
        if re.search(PRIORIDADES[c], texto):
            return c
    return None


def selecionar(manifesto: dict, ds: Dataset, *, eventos: Iterable[str] = (),
               cadernos: Iterable[str] = (), incluir_curso_formacao: bool = False,
               anos: Optional[set[int]] = None, orgaos: Iterable[str] = (),
               prioridade: Iterable[str] = ()) -> tuple[list[dict], list[dict]]:
    """Retorna (candidatas, puladas[{caderno, evento, motivo}]).

    Filtros de priorização: ``anos`` (conjunto), ``orgaos`` (trechos de texto
    casados com evento/órgão, sem acento) e ``prioridade`` (categorias de
    ``PRIORIDADES``, que também definem a ordem). Sem prioridade: mais
    recentes primeiro."""
    evs = {e.upper() for e in eventos}
    cads = {c.upper() for c in cadernos}
    orgs = [discover.norm(o) for o in orgaos if o.strip()]
    prio = [p.strip().lower() for p in prioridade if p.strip()]
    for p in prio:
        if p not in PRIORIDADES:
            raise ValueError(f"prioridade desconhecida: {p!r} (use {', '.join(PRIORIDADES)})")
    cand, pul = [], []
    for e in manifesto["provas"]:
        def pula(motivo: str):
            pul.append({"evento": e["evento"], "caderno": e["caderno"], "motivo": motivo})
        if evs and e["evento"].upper() not in evs:
            continue
        if cads and e["caderno"].upper() not in cads:
            continue
        if anos is not None and e.get("ano") not in anos:
            continue
        if orgs:
            texto = discover.norm(f"{e['evento']} {e.get('evento_nome') or ''} {e.get('orgao', '')}")
            if not any(o in texto for o in orgs):
                continue
        if prio:
            e = dict(e, _categoria=categoria_de(e, prio))
            if e["_categoria"] is None:
                continue
        if not e.get("url_gabarito"):
            pula("sem gabarito definitivo"); continue
        if not e.get("cargos"):
            pula(e.get("cargo_como") or "cargo não identificado"); continue
        if e.get("fase") != "objetiva" and not incluir_curso_formacao:
            pula(f"fase {e.get('fase')}"); continue
        t = tipo_caderno(e.get("descricao", ""))
        if t is not None and t != 1:
            pula(f"caderno TIPO {t} (só o TIPO 1 é ingerido)"); continue
        motivo = ds.ja_ingerida(e)
        if motivo:
            pula(motivo); continue
        cand.append(e)
    # categoria de prioridade (na ordem pedida), depois mais recentes primeiro;
    # dentro do evento, ordem estável do manifesto
    rank = {p: i for i, p in enumerate(prio)}
    cand.sort(key=lambda e: (rank.get(e.get("_categoria"), 0), -(e.get("ano") or 0)))
    return cand, pul


# ---------------------------------------------------------------------------
# Créditos
# ---------------------------------------------------------------------------

def total_ledger(path: Path = usage.LEDGER) -> int:
    if not path.exists():
        return 0
    # usage.py grava com o encoding padrão do sistema (cp1252 no Windows): lê tolerante
    texto = path.read_bytes().decode("utf-8", errors="replace")
    m = re.search(r"\| *All time *\| *(\d+) *\|", texto)
    return int(m.group(1)) if m else 0


def contar_paginas(url: str) -> int:
    pdf = gabmod.baixar(url)
    return max(1, gabmod.pdf_to_text(pdf).count("\f"))


def texto_do_pdf_url(url: str) -> str:
    """Texto corrido do PDF (pdftotext sem -layout), para conferir itens do Firecrawl."""
    import subprocess
    pdf = gabmod.baixar(url)
    out = subprocess.run([gabmod.pdftotext_bin(), "-enc", "UTF-8", str(pdf), "-"],
                         capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace")


def mc_do_pdf_url(url: str, esperados: list[int]) -> dict[int, tuple[str, list[str]]]:
    from . import extract_local
    return extract_local.questoes_mc_do_pdf(gabmod.baixar(url), esperados)


def itens_do_pdf_url(url: str, esperados: list[int]) -> dict[int, str]:
    from . import extract_local
    return extract_local.itens_do_pdf(gabmod.baixar(url), esperados)


def task_de(e: dict) -> str:
    return f"cebraspe-{e.get('ano')}-{e.get('id_orgao')}-{e['caderno']}".lower()


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def extracao_cache(e: dict) -> Path:
    return EXTRACOES / e["evento"] / f"{e['caderno']}.json"


def montar_questoes(e: dict, prova: ProvaExtraida, gab: gabmod.Gabarito) -> list[Questao]:
    out = []
    for c in e["cargos"]:
        meta = ProvaMeta(banca="Cebraspe", orgao=e["orgao"], cargo=c["nome"],
                         ano=e["ano"], fonte=e["url_prova"], assunto=e.get("assunto") or "",
                         id_orgao=e.get("id_orgao"), id_cargo=c.get("id_cargo"))
        for q in prova.questoes:
            g = gab.para_dataset(q.numero)
            if g is None:  # anulado (X) → não vira registro
                continue
            out.append(to_questao(q, meta, gabarito=g))
    return out


@dataclass
class Plano:
    """Decisão (grátis) de qual extrator gera cada item de uma prova."""
    gab: gabmod.Gabarito
    itens_local: Optional[dict[int, str]] = None      # numero → enunciado (C/E ou MC)
    mc_local: Optional[dict[int, tuple[str, list[str]]]] = None  # MC: (enunciado, A–E)
    firecrawl: Optional[str] = None          # None | "itens" | "prova"
    itens_fallback: list[int] = field(default_factory=list)
    motivo: str = ""


EXTRATORES = ("local", "firecrawl", "hibrido")
PdfMC = Callable[[str, list[int]], dict[int, tuple[str, list[str]]]]
MINIMO_QUESTOES_OK = 0.9   # abaixo disso a prova inteira é reprovada


def _cobertura(pl: Plano, gab: gabmod.Gabarito, achados: Iterable[int]) -> bool:
    faltam = sorted(set(gab.itens) - set(achados))
    if faltam:
        cob = 1 - len(faltam) / len(gab.itens)
        pl.firecrawl = "prova"
        pl.motivo = (f"cobertura local {cob:.0%} "
                     f"(faltam {faltam[:8]}{'…' if len(faltam) > 8 else ''})")
        return False
    return True


def planejar(e: dict, gab: gabmod.Gabarito, *, extrator: str,
             pdf_itens: Optional[PdfItens], pdf_mc: Optional[PdfMC] = None) -> Plano:
    """local: só o extrator local. firecrawl: só Firecrawl. hibrido: local, com
    Firecrawl POR ITEM para fórmula ilegível e POR PROVA quando a cobertura não
    fecha com o gabarito. Vale para certo/errado e para múltipla escolha."""
    from . import extract_local
    pl = Plano(gab=gab)
    mc = gab.tipo != "certo_errado"
    leitor = pdf_mc if mc else pdf_itens
    if leitor is not None:
        try:
            lido = leitor(e["url_prova"], gab.itens)
            if mc:
                pl.mc_local = lido
                pl.itens_local = {n: en for n, (en, _) in lido.items()}
            else:
                pl.itens_local = lido
        except Exception as exc:  # noqa: BLE001
            pl.motivo = f"extrator local falhou: {type(exc).__name__}: {exc}"
    if extrator == "firecrawl":
        pl.firecrawl, pl.motivo = "prova", "--extrator firecrawl"
        return pl
    if pl.itens_local is None:
        tipo = "múltipla escolha" if mc else "certo/errado"
        pl.firecrawl, pl.motivo = "prova", pl.motivo or f"extrator local de {tipo} indisponível"
        return pl
    if not _cobertura(pl, gab, pl.itens_local):
        return pl
    # fórmula ilegível só importa em item que vira registro (anulado não entra)
    ileg = extract_local.ilegiveis_mc(pl.mc_local) if mc else \
        extract_local.ilegiveis(pl.itens_local)
    ileg = [n for n in ileg if n not in gab.anulados]
    if ileg:
        pl.firecrawl, pl.itens_fallback = "itens", ileg
        pl.motivo = f"fórmula ilegível nos itens {ileg}"
    return pl


@dataclass
class Resultado:
    entrada: dict
    relatorio: Optional[Relatorio] = None
    status: str = ""                 # aprovada | reprovada | erro | parado
    creditos: int = 0
    cache: bool = False
    adicionadas: int = 0
    colisoes: list[str] = field(default_factory=list)
    mensagem: str = ""
    origem: dict[int, str] = field(default_factory=dict)  # item → local | firecrawl | omitido
    fallback: str = ""
    descartadas: dict[int, list[str]] = field(default_factory=dict)  # item → motivos


def _firecrawl(e: dict, res: Resultado, *, extractor: Extractor, ledger: Path,
               estimativa: int) -> Optional[ProvaExtraida]:
    """Extração Firecrawl da prova inteira (cache → zero crédito)."""
    cpath = extracao_cache(e)
    if cpath.exists():
        res.cache = True
        return ProvaExtraida.model_validate_json(cpath.read_text(encoding="utf-8"))
    antes = total_ledger(ledger)
    try:
        prova = extractor(e["url_prova"], task_de(e))
    except Exception as exc:  # noqa: BLE001
        res.creditos = total_ledger(ledger) - antes
        res.status, res.mensagem = "erro", f"extração: {type(exc).__name__}: {exc}"
        return None
    res.creditos = total_ledger(ledger) - antes
    if res.creditos <= 0:
        # extract_prova só registra quando a resposta traz creditsUsed
        usage.log_call(task=task_de(e), tool="sdk:scrape[json]", items=1,
                       credits=estimativa, path=ledger,
                       notes=f"{e['url_prova']} - creditsUsed ausente; estimativa run.py")
        res.creditos = estimativa
        res.mensagem = "creditsUsed ausente na resposta: estimativa registrada no ledger"
    cpath.parent.mkdir(parents=True, exist_ok=True)
    cpath.write_text(prova.model_dump_json(indent=2), encoding="utf-8")
    return prova


def _da_local(plano: Plano, numeros: Iterable[int]) -> list[QuestaoExtraida]:
    out = []
    for n in sorted(numeros):
        if plano.mc_local is not None:
            if n in plano.mc_local:
                en, alts = plano.mc_local[n]
                out.append(QuestaoExtraida(numero=n, enunciado=en, alternativas=alts))
        elif n in (plano.itens_local or {}):
            out.append(QuestaoExtraida(numero=n, enunciado=plano.itens_local[n],
                                       alternativas=["Certo", "Errado"]))
    return out


# Erros de validação atribuíveis a UMA questão no cruzamento com o PDF: geram
# descarte por questão (se ≥ 90% passam). Os demais reprovam a prova inteira.
ERROS_DE_QUESTAO = ("enunciado não encontrado no texto do PDF",
                    "alternativa não encontrada no texto do PDF",
                    "enunciado não confere com o texto do item no PDF")


def processar(e: dict, ds: Dataset, *, plano: Plano, extrator: str, extractor: Extractor,
              ledger: Path, estimativa: int,
              pdf_texto: Optional[Callable[[str], str]] = None) -> Resultado:
    res = Resultado(entrada=e, fallback=plano.motivo)
    gab = plano.gab
    omitidos: list[int] = []

    if plano.firecrawl is None:                         # 100% local, zero crédito
        prova = ProvaExtraida(questoes=_da_local(plano, gab.itens))
        res.origem = {q.numero: "local" for q in prova.questoes}
    elif extrator == "local":                           # nunca gasta crédito
        if plano.firecrawl == "prova":
            res.status, res.mensagem = "erro", f"--extrator local: {plano.motivo}"
            return res
        omitidos = plano.itens_fallback                 # fórmula ilegível fica de fora
        prova = ProvaExtraida(questoes=_da_local(
            plano, [n for n in gab.itens if n not in omitidos]))
        res.origem = {q.numero: "local" for q in prova.questoes}
        res.origem.update({n: "omitido (fórmula ilegível)" for n in omitidos})
    else:
        fc = _firecrawl(e, res, extractor=extractor, ledger=ledger, estimativa=estimativa)
        if fc is None:
            return res
        if plano.firecrawl == "prova":
            prova = fc
            res.origem = {q.numero: "firecrawl" for q in prova.questoes}
        else:                                           # por item: só as fórmulas
            do_fc = {q.numero: q for q in fc.questoes}
            questoes = _da_local(plano, [n for n in gab.itens if n not in plano.itens_fallback])
            res.origem = {q.numero: "local" for q in questoes}
            for n in plano.itens_fallback:
                if n in do_fc:
                    alts = do_fc[n].alternativas if plano.mc_local is not None \
                        else ["Certo", "Errado"]
                    questoes.append(QuestaoExtraida(numero=n, enunciado=do_fc[n].enunciado,
                                                    alternativas=alts))
                    res.origem[n] = "firecrawl"
            prova = ProvaExtraida(questoes=sorted(questoes, key=lambda q: q.numero))

    # validação (+ cruzamento com o texto do PDF, grátis). Texto conferido: itens
    # do Firecrawl e, em múltipla escolha, todas as questões.
    mc = gab.tipo != "certo_errado"
    # questão anulada não vira registro: não é cruzada com o PDF
    verificar = [q.numero for q in prova.questoes if q.numero not in gab.anulados] if mc else \
        [n for n, o in res.origem.items() if o == "firecrawl" and n not in gab.anulados]
    texto = None
    if verificar and pdf_texto is not None:
        try:
            texto = pdf_texto(e["url_prova"])
        except Exception:  # noqa: BLE001 — sem texto, sem essa conferência
            texto = None

    def _validar(prova_v: ProvaExtraida, fora: Iterable[int]) -> Relatorio:
        fora = set(fora)
        gab_v = gab if not fora else gabmod.Gabarito(
            respostas={n: r for n, r in gab.respostas.items() if n not in fora}, url=gab.url)
        return validar(prova_v, gab_v, caderno=f"{e['evento']}/{e['caderno']}",
                       url_prova=e["url_prova"], url_gabarito=e["url_gabarito"],
                       itens_pdf=plano.itens_local,
                       so_indicativo=set(plano.itens_fallback) | set(gab.anulados),
                       texto_pdf=texto, verificar_texto=[n for n in verificar if n not in fora])

    rel = _validar(prova, omitidos)

    # descarte POR QUESTÃO: só falhas de cruzamento com o PDF, e só se ≥ 90%
    # das questões válidas passam; senão (ou com erro de prova) reprova inteira
    if not rel.aprovada:
        erros_prova = [x for x in rel.erros if not x.startswith(ERROS_DE_QUESTAO)]
        falhas = {n: m for n, m in rel.falhas_por_questao.items()
                  if n not in gab.anulados and any(
                      x.startswith(("enunciado não", "alternativa")) for x in m)}
        validas = len([n for n in gab.itens if n not in gab.anulados and n not in omitidos])
        taxa = (validas - len(falhas)) / max(1, validas)
        if not erros_prova and falhas and taxa >= MINIMO_QUESTOES_OK:
            prova2 = ProvaExtraida(questoes=[q for q in prova.questoes if q.numero not in falhas])
            rel2 = _validar(prova2, set(omitidos) | set(falhas))
            if rel2.aprovada:
                prova, rel = prova2, rel2
                res.descartadas = falhas
                res.origem.update({n: "descartada (falha no PDF)" for n in falhas})
                rel.avisos.append(f"{len(falhas)} questão(ões) descartada(s) no cruzamento com "
                                  f"o PDF ({taxa:.0%} aprovadas): "
                                  + "; ".join(f"{n}: {', '.join(m)}" for n, m in sorted(falhas.items())))
        elif falhas and not erros_prova:
            rel.erros.append(f"só {taxa:.0%} das questões passaram no cruzamento com o PDF "
                             f"(mínimo {MINIMO_QUESTOES_OK:.0%}): prova reprovada inteira")

    if plano.motivo and plano.firecrawl and extrator != "local":
        rel.avisos.append(f"fallback Firecrawl ({plano.firecrawl}): {plano.motivo}")
    if omitidos:
        rel.avisos.append(f"--extrator local: itens com fórmula ilegível omitidos: {omitidos}")
    res.relatorio = rel
    if not rel.aprovada:
        res.status = "reprovada"
        return res

    try:
        novas = montar_questoes(e, prova, gab)
    except ValueError as exc:
        rel.aprovada = False
        rel.erros.append(f"to_questao: {exc}")
        res.status = "reprovada"
        return res
    res.adicionadas, res.colisoes = ds.append(novas)
    res.status = "aprovada"
    return res


def custo_estimado(e: dict, plano: Plano, page_counter: PageCounter) -> int:
    """Créditos que esta prova vai gastar (0 se 100% local ou já em cache)."""
    if plano.firecrawl is None or extracao_cache(e).exists():
        return 0
    return page_counter(e["url_prova"]) + CUSTO_FIXO


def executar(manifesto: dict, ds: Dataset, *, limite: int, teto: int,
             extractor: Extractor, gab_loader: GabLoader, page_counter: PageCounter,
             ledger: Path = usage.LEDGER, eventos: Iterable[str] = (),
             cadernos: Iterable[str] = (), incluir_curso_formacao: bool = False,
             pdf_itens: Optional[PdfItens] = None, extrator: str = "hibrido",
             filtros: Optional[dict] = None,
             pdf_texto: Optional[Callable[[str], str]] = None,
             pdf_mc: Optional[PdfMC] = None, log=print) -> dict:
    cand, pul = selecionar(manifesto, ds, eventos=eventos, cadernos=cadernos,
                           incluir_curso_formacao=incluir_curso_formacao, **(filtros or {}))
    gasto = 0
    resultados: list[Resultado] = []
    parado = None
    for e in cand:
        if len(resultados) >= limite:
            break
        # gabarito e extrator local primeiro: grátis; se falharem, nada é gasto
        try:
            gab = gab_loader(e["url_gabarito"])
        except Exception as exc:  # noqa: BLE001
            resultados.append(Resultado(entrada=e, status="erro",
                                        mensagem=f"gabarito: {type(exc).__name__}: {exc}"))
            continue
        plano = planejar(e, gab, extrator=extrator, pdf_itens=pdf_itens, pdf_mc=pdf_mc)
        est = 0
        if extrator != "local":
            try:
                est = custo_estimado(e, plano, page_counter)
            except Exception as exc:  # noqa: BLE001
                resultados.append(Resultado(entrada=e, status="erro",
                                            mensagem=f"download da prova: {exc}"))
                continue
            if est and gasto + est > teto:
                parado = (f"teto de créditos: gasto {gasto} + estimativa {est} "
                          f"> {teto} ({e['caderno']})")
                log(f"PARANDO — {parado}")
                break
        modo = "local" if plano.firecrawl is None else f"firecrawl/{plano.firecrawl}"
        log(f"→ {e['evento']}/{e['caderno']} ({len(e['cargos'])} cargo(s), {modo}, "
            f"estimativa {est} créditos)")
        r = processar(e, ds, plano=plano, extrator=extrator, extractor=extractor,
                      ledger=ledger, estimativa=est, pdf_texto=pdf_texto)
        gasto += r.creditos
        resultados.append(r)
        if r.relatorio:
            log(formatar(r.relatorio))
        if r.mensagem:
            log(f"  {r.status}: {r.mensagem}")
        if r.status == "aprovada":
            log(f"  +{r.adicionadas} questões no dataset"
                + (f" ({len(r.colisoes)} ids já existentes ignorados)" if r.colisoes else ""))
        log(f"  créditos: {r.creditos}{' (cache)' if r.cache else ''} | acumulado {gasto}/{teto}")

    if any(r.adicionadas for r in resultados):
        ds.salvar()
    return {
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "extrator": extrator,
        "limite_provas": limite,
        "teto_creditos": teto,
        "creditos_gastos": gasto,
        "parado": parado,
        "candidatas": len(cand),
        "puladas": len(pul),
        "provas": [{
            "evento": r.entrada["evento"],
            "caderno": r.entrada["caderno"],
            "cargos": [c["nome"] for c in r.entrada["cargos"]],
            "status": r.status,
            "creditos": r.creditos,
            "cache": r.cache,
            "adicionadas": r.adicionadas,
            "colisoes": r.colisoes,
            "mensagem": r.mensagem,
            "fallback": r.fallback,
            "itens_por_extrator": dict(Counter(r.origem.values())),
            "extrator_por_item": {str(n): o for n, o in sorted(r.origem.items())},
            "questoes_descartadas": {str(n): m for n, m in sorted(r.descartadas.items())},
            "validacao": r.relatorio.to_dict() if r.relatorio else None,
        } for r in resultados],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def estimar_custo(cand: list[dict], *, amostra: int, gab_loader: GabLoader,
                  pdf_itens: PdfItens, page_counter: PageCounter, semente: int = 0,
                  pdf_mc: Optional[PdfMC] = None,
                  log=print) -> dict:
    """Custo (só fallbacks Firecrawl) do modo híbrido. Grátis: baixa gabarito e
    prova e roda o extrator local; exato se a seleção cabe na amostra, senão
    extrapola a média da amostra aleatória para o total."""
    import random
    sel = cand if len(cand) <= amostra else random.Random(semente).sample(cand, amostra)
    tipos: Counter = Counter()
    custos: list[int] = []
    for i, e in enumerate(sel, 1):
        if i % 20 == 0:
            log(f"  … estimando {i}/{len(sel)}")
        try:
            gab = gab_loader(e["url_gabarito"])
            pl = planejar(e, gab, extrator="hibrido", pdf_itens=pdf_itens, pdf_mc=pdf_mc)
            c = custo_estimado(e, pl, page_counter)
        except Exception:  # noqa: BLE001 — prova sem gabarito/PDF legível não é processada
            tipos["erro (não processada, 0 crédito)"] += 1
            custos.append(0)
            continue
        if pl.firecrawl is None:
            tipos["100% local"] += 1
        elif pl.firecrawl == "itens":
            tipos["fallback por item (fórmula)"] += 1
        elif "múltipla escolha" in pl.motivo or pl.gab.tipo != "certo_errado":
            tipos["fallback por prova (múltipla escolha)"] += 1
        else:
            tipos["fallback por prova (cobertura)"] += 1
        custos.append(c)
    media = sum(custos) / max(1, len(custos))
    return {
        "provas": len(cand), "amostra": len(sel), "exato": len(sel) == len(cand),
        "creditos_amostra": sum(custos), "media_por_prova": round(media, 2),
        "estimativa_total": round(media * len(cand)), "por_tipo": dict(tipos),
    }


def _filtros(args) -> dict:
    return {"anos": parse_anos(args.anos), "orgaos": args.orgao,
            "prioridade": [p for p in (args.prioridade or "").split(",") if p.strip()]}


def plano(manifesto: dict, ds: Dataset, args) -> int:
    cand, pul = selecionar(manifesto, ds, eventos=args.evento, cadernos=args.caderno,
                           incluir_curso_formacao=args.incluir_curso_formacao, **_filtros(args))
    print(f"manifesto: {manifesto['resumo']}")
    print(f"candidatas: {len(cand)} provas em {len({e['evento'] for e in cand})} eventos "
          f"| puladas: {len(pul)}")
    if any(e.get("_categoria") for e in cand):
        for cat, n in Counter(e["_categoria"] for e in cand).items():
            print(f"  prioridade {cat}: {n} provas")
    for motivo, n in Counter(p["motivo"] for p in pul).most_common(8):
        print(f"  pulada ({n}): {motivo}")
    if args.estimar_custo:
        est = estimar_custo(cand, amostra=args.amostra, gab_loader=gabmod.carregar,
                            pdf_itens=itens_do_pdf_url, page_counter=contar_paginas,
                            pdf_mc=mc_do_pdf_url,
                            semente=args.semente)
        tipo = "exato" if est["exato"] else f"amostra de {est['amostra']}"
        print(f"custo estimado (só fallbacks, {tipo}): ~{est['estimativa_total']} créditos "
              f"(média {est['media_por_prova']}/prova; amostra gastaria {est['creditos_amostra']})")
        for t, n in sorted(est["por_tipo"].items(), key=lambda x: -x[1]):
            print(f"  {t}: {n}/{est['amostra']}")
    print(f"próximas {min(args.limite_provas or 10, len(cand))} (dry-run, zero créditos):")
    for e in cand[: args.limite_provas or 10]:
        cs = ", ".join(c["nome"] for c in e["cargos"][:3])
        mais = f" +{len(e['cargos']) - 3}" if len(e["cargos"]) > 3 else ""
        cad = e["caderno"] if len(e["caderno"]) <= 28 else e["caderno"][:12] + "…"
        print(f"  {e['ano']} {e['evento']:<22} {cad:<28} {e['assunto'] or '-':<26} "
              f"{cs}{mais}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Pipeline Cebraspe: manifesto → dataset")
    ap.add_argument("--dry-run", action="store_true", help="só descoberta/plano, zero créditos")
    ap.add_argument("--limite-provas", type=int, default=None, help="máx. de provas a processar")
    ap.add_argument("--teto-creditos", type=int, default=None,
                    help="para antes de ultrapassar N créditos Firecrawl (obrigatório fora do dry-run)")
    ap.add_argument("--evento", action="append", default=[], help="filtra por eventoURL")
    ap.add_argument("--caderno", action="append", default=[], help="filtra por caderno")
    ap.add_argument("--descobrir", action="store_true", help="regera o manifesto antes (grátis)")
    ap.add_argument("--incluir-curso-formacao", action="store_true")
    ap.add_argument("--anos", help="ex.: 2022-2026 ou 2021,2023")
    ap.add_argument("--orgao", action="append", default=[],
                    help="trecho do órgão/evento (sem acento/maiúscula), repetível")
    ap.add_argument("--prioridade",
                    help="categorias em ordem, separadas por vírgula: " + ",".join(PRIORIDADES))
    ap.add_argument("--estimar-custo", action="store_true",
                    help="no --dry-run: estima créditos dos fallbacks (grátis; baixa PDFs)")
    ap.add_argument("--amostra", type=int, default=60,
                    help="provas usadas na estimativa (exata se a seleção couber)")
    ap.add_argument("--semente", type=int, default=0)
    ap.add_argument("--extrator", choices=EXTRATORES, default="hibrido",
                    help="local (zero crédito), firecrawl, ou hibrido (padrão: local + "
                         "Firecrawl por item p/ fórmula e por prova p/ cobertura incompleta)")
    ap.add_argument("--manifesto", type=Path, default=discover.MANIFEST)
    ap.add_argument("--dataset", type=Path, default=DATASET)
    args = ap.parse_args(argv)

    if args.descobrir or not args.manifesto.exists():
        discover.salvar(discover.descobrir(discover.make_fetch()), args.manifesto)
    manifesto = json.loads(args.manifesto.read_text(encoding="utf-8"))
    ds = Dataset.carregar(args.dataset)

    if args.dry_run:
        return plano(manifesto, ds, args)

    if args.limite_provas is None or (args.teto_creditos is None and args.extrator != "local"):
        ap.error("--limite-provas (e --teto-creditos, exceto com --extrator local) são "
                 "obrigatórios fora do --dry-run")
    if args.extrator == "local":
        args.teto_creditos = 0

    app = None

    def extractor(url: str, task: str) -> ProvaExtraida:
        nonlocal app
        from .extract import extract_prova, make_app  # só importa/abre a chave se for gastar
        if app is None:
            app = make_app()
        return extract_prova(app, url, task=task)

    rep = executar(manifesto, ds, limite=args.limite_provas, teto=args.teto_creditos,
                   extractor=extractor, gab_loader=gabmod.carregar,
                   page_counter=contar_paginas, pdf_itens=itens_do_pdf_url,
                   pdf_texto=texto_do_pdf_url, pdf_mc=mc_do_pdf_url,
                   extrator=args.extrator, eventos=args.evento, cadernos=args.caderno,
                   filtros=_filtros(args),
                   incluir_curso_formacao=args.incluir_curso_formacao)
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"run-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(p["status"] == "aprovada" for p in rep["provas"])
    print(f"\nresumo: {ok}/{len(rep['provas'])} aprovadas | créditos {rep['creditos_gastos']}"
          f"/{rep['teto_creditos']} | relatório: {out}")
    return 0 if all(p["status"] == "aprovada" for p in rep["provas"]) else 1


if __name__ == "__main__":
    sys.exit(main())
