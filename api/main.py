"""papiro API — read-only FastAPI over the questao store (crawler/db.py).

Endpoints (surface mínima do plano docker-postgres):

    GET /health                       probe do compose
    GET /filtros?…&dims=              opções dos Selects (cascata; dims limita dimensões)
    GET /filtros/{dim}?q=&limit=      facetas de uma dimensão (busca + top-N p/ combobox)
    GET /questoes?…&page&per_page     lista paginada filtrada (inclui evento= e fonte=)
    GET /questoes/{id}                detalhe
    GET /eventos                      concursos ingeridos (contagens + orgaos/cargos/anos)
    GET /provas?evento=               provas por evento (fonte + cargos/anos/tipos)

Respostas usam o shape flat de ``crawler.models.Questao`` — o mesmo que
``shard_to_records`` emite e ``web/src/data/questions.ts`` tipifica.

    DATABASE_URL  postgres(psycopg) — default postgresql+psycopg://localhost/papiro
    CORS_ORIGINS  origens separadas por vírgula — default GitHub Pages
"""

from __future__ import annotations

import math
import os
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import String, cast, func, select, text
from sqlalchemy.orm import Session

from crawler.db import (DEFAULT_URL, Assunto, Banca, Cargo, Evento, Orgao,
                        Prova, QuestaoDB, get_engine)
from crawler.models import Questao

from . import queries


class QuestaoPage(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int
    items: list[Questao]


class Filtros(BaseModel):
    bancas: Optional[list[str]] = None
    orgaos: Optional[list[str]] = None
    cargos: Optional[list[str]] = None
    anos: Optional[list[int]] = None
    assuntos: Optional[list[str]] = None


class Faceta(BaseModel):
    valor: str
    questoes: int


class EventoInfo(BaseModel):
    evento: str
    banca: str
    questoes: int
    provas: int
    orgaos: list[str]
    cargos: list[str]
    anos: list[int]


class ProvaInfo(BaseModel):
    evento: str
    fonte: str
    questoes: int
    cargos: list[str]
    anos: list[int]
    tipos: list[str]


DEFAULT_CORS = "https://olavostauros.github.io,http://localhost:4321"
MAX_PER_PAGE = 100
MAX_PAGE = 10000               # teto p/ OFFSET arbitrário (DoS barato)
MAX_FACETAS = 500              # teto p/ /filtros/{dim}?limit=
STATEMENT_TIMEOUT_MS = 5000    # postgres apenas; SQLite nos testes ignora

Tipo = Literal["certo_errado", "multipla_escolha"]

# dimensão (path/query) → (coluna, campo em Filtros); a chave é também o
# nome do filtro em queries.apply_filters.
DIMS = {
    "banca": (Banca.nome, "bancas"),
    "orgao": (Orgao.nome, "orgaos"),
    "cargo": (Cargo.nome, "cargos"),
    "ano": (QuestaoDB.ano, "anos"),
    "assunto": (Assunto.nome, "assuntos"),
}


def create_app(database_url: Optional[str] = None) -> FastAPI:
    url = database_url or os.environ.get("DATABASE_URL") or DEFAULT_URL
    kw = {"connect_args": {
        "options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}"}} \
        if url.startswith("postgres") else {}
    engine = get_engine(url, **kw)
    if url.startswith("postgres"):
        try:  # usuário sem privilégio de extensão — a sonda abaixo decide
            with engine.begin() as c:
                c.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        except Exception:
            pass
    try:  # DB fora do ar no boot não deve derrubar o import — degrada
        with engine.connect() as c:
            c.execute(text("SELECT unaccent('e')"))
        queries.USE_UNACCENT = True
    except Exception:
        queries.USE_UNACCENT = False
    app = FastAPI(title="papiro API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("CORS_ORIGINS", DEFAULT_CORS).split(","),
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    def session():
        with Session(engine) as s:
            yield s

    @app.get("/health")
    def health(s: Session = Depends(session)):
        s.execute(text("SELECT 1"))
        return {"status": "ok"}

    def filtros_kw(banca, orgao, cargo, ano, assunto, tipo, q, evento, fonte):
        return dict(banca=banca, orgao=orgao, cargo=cargo, ano=ano,
                    assunto=assunto, tipo=tipo, q=q, evento=evento,
                    fonte=fonte)

    @app.get("/filtros", response_model=Filtros,
             response_model_exclude_none=True)
    def filtros(
        s: Session = Depends(session),
        banca: Optional[str] = None, orgao: Optional[str] = None,
        cargo: Optional[str] = None, ano: Optional[int] = None,
        assunto: Optional[str] = None, tipo: Optional[Tipo] = None,
        q: Optional[str] = None, evento: Optional[str] = None,
        fonte: Optional[str] = None,
        dims: Optional[str] = None,
    ):
        wanted = set(dims.split(",")) if dims else set(DIMS)
        if bad := wanted - set(DIMS):
            raise HTTPException(422, f"dims desconhecidas: {sorted(bad)}")
        kw = filtros_kw(banca, orgao, cargo, ano, assunto, tipo, q, evento,
                        fonte)
        out = {}
        for dim, (col, field) in DIMS.items():
            if dim not in wanted:
                continue
            vals = queries.distinct_values(s, col, exclude=dim, **kw)
            out[field] = sorted(vals, reverse=(dim == "ano"))
        return Filtros(**out)

    @app.get("/filtros/{dim}", response_model=list[Faceta])
    def faceta(
        dim: str,
        s: Session = Depends(session),
        banca: Optional[str] = None, orgao: Optional[str] = None,
        cargo: Optional[str] = None, ano: Optional[int] = None,
        assunto: Optional[str] = None, tipo: Optional[Tipo] = None,
        evento: Optional[str] = None, fonte: Optional[str] = None,
        q: Optional[str] = None,
        limit: int = Query(50, ge=1, le=MAX_FACETAS),
    ):
        spec = DIMS.get(dim)
        if spec is None:
            raise HTTPException(404, f"dimensão desconhecida: {dim}")
        col, _ = spec
        stmt = queries.apply_filters(
            select(col, func.count(QuestaoDB.id))
            .select_from(QuestaoDB)
            .join(Prova, QuestaoDB.prova_id == Prova.id)
            .join(Evento, Prova.evento_id == Evento.id)
            .join(Banca, Evento.banca_id == Banca.id)
            .join(Cargo, QuestaoDB.cargo_id == Cargo.id)
            .join(Orgao, Cargo.orgao_id == Orgao.id)
            .outerjoin(Assunto, QuestaoDB.assunto_id == Assunto.id)
            .group_by(col),
            exclude=dim,
            **filtros_kw(banca, orgao, cargo, ano, assunto, tipo, None,
                         evento, fonte))
        if q:
            stmt = stmt.where(
                queries.unaccent_ilike(cast(col, String), q))
        order = col.desc() if dim == "ano" else func.count().desc()
        rows = s.execute(stmt.order_by(order, col).limit(limit))
        return [Faceta(valor=str(v), questoes=c)
                for v, c in rows if v is not None]

    @app.get("/questoes", response_model=QuestaoPage)
    def questoes(
        s: Session = Depends(session),
        banca: Optional[str] = None, orgao: Optional[str] = None,
        cargo: Optional[str] = None, ano: Optional[int] = None,
        assunto: Optional[str] = None, tipo: Optional[Tipo] = None,
        q: Optional[str] = None, evento: Optional[str] = None,
        fonte: Optional[str] = None,
        page: int = Query(1, ge=1, le=MAX_PAGE),
        per_page: int = Query(20, ge=1, le=MAX_PER_PAGE),
    ):
        kw = filtros_kw(banca, orgao, cargo, ano, assunto, tipo, q, evento,
                        fonte)
        stmt = queries.apply_filters(queries.base_questao(), **kw)
        count_stmt = queries.apply_filters(
            select(func.count()).select_from(QuestaoDB)
            .join(Prova, QuestaoDB.prova_id == Prova.id)
            .join(Evento, Prova.evento_id == Evento.id)
            .join(Banca, Evento.banca_id == Banca.id)
            .join(Cargo, QuestaoDB.cargo_id == Cargo.id)
            .join(Orgao, Cargo.orgao_id == Orgao.id)
            .outerjoin(Assunto, QuestaoDB.assunto_id == Assunto.id),
            **kw)
        total = s.scalar(count_stmt) or 0
        rows = s.execute(
            stmt.order_by(QuestaoDB.ano.desc(), QuestaoDB.id)
                .offset((page - 1) * per_page).limit(per_page)).all()
        return QuestaoPage(
            total=total, page=page, per_page=per_page,
            pages=math.ceil(total / per_page) if total else 0,
            items=[Questao(**queries.row_to_questao(r)) for r in rows])

    @app.get("/questoes/{questao_id}", response_model=Questao)
    def questao(questao_id: str, s: Session = Depends(session)):
        row = s.execute(
            queries.base_questao().where(QuestaoDB.id == questao_id)
        ).first()
        if row is None:
            raise HTTPException(404, "questão não encontrada")
        return Questao(**queries.row_to_questao(row))

    @app.get("/eventos", response_model=list[EventoInfo])
    def eventos(s: Session = Depends(session)):
        counts = s.execute(
            select(Evento.evento, Banca.nome,
                   func.count(QuestaoDB.id).label("questoes"),
                   func.count(func.distinct(Prova.id)).label("provas"))
            .select_from(Evento)
            .join(Banca, Evento.banca_id == Banca.id)
            .join(Prova, Prova.evento_id == Evento.id)
            .join(QuestaoDB, QuestaoDB.prova_id == Prova.id)
            .group_by(Evento.id, Evento.evento, Banca.nome)
            .order_by(Evento.evento)
        ).all()
        dims = s.execute(
            select(Evento.evento, Orgao.nome, Cargo.nome, QuestaoDB.ano)
            .select_from(Evento)
            .join(Prova, Prova.evento_id == Evento.id)
            .join(QuestaoDB, QuestaoDB.prova_id == Prova.id)
            .join(Cargo, QuestaoDB.cargo_id == Cargo.id)
            .join(Orgao, Cargo.orgao_id == Orgao.id)
            .distinct()
        ).all()
        detalhes: dict[str, dict[str, set]] = {}
        for ev, org, cargo, ano in dims:
            d = detalhes.setdefault(
                ev, {"orgaos": set(), "cargos": set(), "anos": set()})
            d["orgaos"].add(org)
            d["cargos"].add(cargo)
            d["anos"].add(ano)
        vazio = {"orgaos": set(), "cargos": set(), "anos": set()}
        return [EventoInfo(evento=r.evento, banca=r.nome,
                           questoes=r.questoes, provas=r.provas,
                           orgaos=sorted(d["orgaos"]),
                           cargos=sorted(d["cargos"]),
                           anos=sorted(d["anos"], reverse=True))
                for r in counts for d in [detalhes.get(r.evento, vazio)]]

    @app.get("/provas", response_model=list[ProvaInfo])
    def provas(s: Session = Depends(session), evento: Optional[str] = None):
        stmt = (
            select(Evento.evento, Prova.id, Prova.fonte,
                   func.count(QuestaoDB.id).label("questoes"))
            .select_from(Prova)
            .join(Evento, Prova.evento_id == Evento.id)
            .outerjoin(QuestaoDB, QuestaoDB.prova_id == Prova.id)
            .group_by(Prova.id, Evento.evento, Prova.fonte)
            .order_by(Evento.evento, Prova.fonte)
        )
        dims = (
            select(Prova.id, Cargo.nome, QuestaoDB.ano, QuestaoDB.tipo)
            .select_from(Prova)
            .join(Evento, Prova.evento_id == Evento.id)
            .join(QuestaoDB, QuestaoDB.prova_id == Prova.id)
            .join(Cargo, QuestaoDB.cargo_id == Cargo.id)
            .distinct()
        )
        if evento:
            stmt = stmt.where(Evento.evento == evento)
            dims = dims.where(Evento.evento == evento)
        detalhes: dict[int, dict[str, set]] = {}
        for pid, cargo, ano, tipo in s.execute(dims):
            d = detalhes.setdefault(
                pid, {"cargos": set(), "anos": set(), "tipos": set()})
            d["cargos"].add(cargo)
            d["anos"].add(ano)
            d["tipos"].add(tipo)
        vazio = {"cargos": set(), "anos": set(), "tipos": set()}
        return [ProvaInfo(evento=r.evento, fonte=r.fonte,
                          questoes=r.questoes,
                          cargos=sorted(d["cargos"]),
                          anos=sorted(d["anos"], reverse=True),
                          tipos=sorted(d["tipos"]))
                for r in s.execute(stmt)
                for d in [detalhes.get(r.id, vazio)]]

    return app


app = create_app()
