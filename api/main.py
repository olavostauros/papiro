"""papiro API — read-only FastAPI over the questao store (crawler/db.py).

Endpoints (surface mínima do plano docker-postgres):

    GET /health                       probe do compose
    GET /filtros?banca&orgao&cargo&ano&assunto&tipo&q   opções dos Selects (cascata)
    GET /questoes?…&page&per_page     lista paginada filtrada
    GET /questoes/{id}                detalhe
    GET /eventos                      concursos ingeridos (contagens)
    GET /provas?evento=               provas (fonte) por evento

Respostas usam o shape flat de ``crawler.models.Questao`` — o mesmo que
``shard_to_records`` emite e ``web/src/data/questions.ts`` tipifica.

    DATABASE_URL  postgres(psycopg) — default postgresql+psycopg://localhost/papiro
    CORS_ORIGINS  origens separadas por vírgula — default GitHub Pages
"""

from __future__ import annotations

import math
import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from crawler.db import (Assunto, Banca, Cargo, Evento, Orgao, Prova,
                        QuestaoDB, get_engine)
from crawler.models import Questao

from . import queries


class QuestaoPage(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int
    items: list[Questao]


class Filtros(BaseModel):
    bancas: list[str]
    orgaos: list[str]
    cargos: list[str]
    anos: list[int]
    assuntos: list[str]


class EventoInfo(BaseModel):
    evento: str
    banca: str
    questoes: int
    provas: int


class ProvaInfo(BaseModel):
    evento: str
    fonte: str
    questoes: int


DEFAULT_CORS = "https://olavostauros.github.io"
MAX_PER_PAGE = 100


def create_app(database_url: Optional[str] = None) -> FastAPI:
    engine = get_engine(database_url)
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

    @app.get("/filtros", response_model=Filtros)
    def filtros(
        s: Session = Depends(session),
        banca: Optional[str] = None, orgao: Optional[str] = None,
        cargo: Optional[str] = None, ano: Optional[int] = None,
        assunto: Optional[str] = None, tipo: Optional[str] = None,
        q: Optional[str] = None,
    ):
        kw = dict(banca=banca, orgao=orgao, cargo=cargo, ano=ano,
                  assunto=assunto, tipo=tipo, q=q)
        dv = lambda col, ex: queries.distinct_values(s, col, exclude=ex, **kw)
        return Filtros(
            bancas=sorted(dv(Banca.nome, "banca")),
            orgaos=sorted(dv(Orgao.nome, "orgao")),
            cargos=sorted(dv(Cargo.nome, "cargo")),
            anos=sorted(dv(QuestaoDB.ano, "ano"), reverse=True),
            assuntos=sorted(dv(Assunto.nome, "assunto")),
        )

    @app.get("/questoes", response_model=QuestaoPage)
    def questoes(
        s: Session = Depends(session),
        banca: Optional[str] = None, orgao: Optional[str] = None,
        cargo: Optional[str] = None, ano: Optional[int] = None,
        assunto: Optional[str] = None, tipo: Optional[str] = None,
        q: Optional[str] = None,
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=MAX_PER_PAGE),
    ):
        stmt = queries.apply_filters(
            queries.base_questao(), banca=banca, orgao=orgao, cargo=cargo,
            ano=ano, assunto=assunto, tipo=tipo, q=q)
        count_stmt = queries.apply_filters(
            select(func.count()).select_from(QuestaoDB)
            .join(Prova, QuestaoDB.prova_id == Prova.id)
            .join(Evento, Prova.evento_id == Evento.id)
            .join(Banca, Evento.banca_id == Banca.id)
            .join(Cargo, QuestaoDB.cargo_id == Cargo.id)
            .join(Orgao, Cargo.orgao_id == Orgao.id)
            .outerjoin(Assunto, QuestaoDB.assunto_id == Assunto.id),
            banca=banca, orgao=orgao, cargo=cargo, ano=ano, assunto=assunto,
            tipo=tipo, q=q)
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
        rows = s.execute(
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
        return [EventoInfo(evento=r.evento, banca=r.nome,
                           questoes=r.questoes, provas=r.provas)
                for r in rows]

    @app.get("/provas", response_model=list[ProvaInfo])
    def provas(s: Session = Depends(session), evento: Optional[str] = None):
        stmt = (
            select(Evento.evento, Prova.fonte,
                   func.count(QuestaoDB.id).label("questoes"))
            .select_from(Prova)
            .join(Evento, Prova.evento_id == Evento.id)
            .outerjoin(QuestaoDB, QuestaoDB.prova_id == Prova.id)
            .group_by(Prova.id, Evento.evento, Prova.fonte)
            .order_by(Evento.evento, Prova.fonte)
        )
        if evento:
            stmt = stmt.where(Evento.evento == evento)
        return [ProvaInfo(evento=r.evento, fonte=r.fonte, questoes=r.questoes)
                for r in s.execute(stmt)]

    return app


app = create_app()
