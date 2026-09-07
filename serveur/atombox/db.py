"""LA BASE (D154, D158) — SQLAlchemy 2 ORM sur psycopg 3, synchrone pour le démon (qui tourne
dans des threads), asynchrone pour l'API. Les modèles sont ENGENDRÉS (schema/modeles.py) ;
aucun module ne compose de SQL — un test le vérifie."""
from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .journal import journal

log = journal("schema")

def normaliser(u: str) -> str:
    """toujours psycopg 3 (D154) : SQLAlchemy prendrait psycopg2 sur un simple postgresql://"""
    return u.replace("postgresql://", "postgresql+psycopg://", 1) if u.startswith("postgresql://") else u

def url() -> str:
    u = os.environ.get("DATABASE_URL")
    if not u: raise SystemExit("DATABASE_URL absent — ex. postgresql:///atombox")
    return normaliser(u)

_sync = {}; _async = {}

def moteur(u: str | None = None):
    u = normaliser(u) if u else url()
    if u not in _sync:
        log.debug("moteur synchrone : %s", u.split("@")[-1]); _sync[u] = create_engine(u, pool_pre_ping=True)
    return _sync[u]

def session(u: str | None = None) -> Session:
    return sessionmaker(moteur(u), expire_on_commit=False)()

def moteur_async(u: str | None = None):
    u = normaliser(u) if u else url()
    if u not in _async:
        log.debug("moteur asynchrone : %s", u.split("@")[-1]); _async[u] = create_async_engine(u, pool_pre_ping=True)
    return _async[u]

def fabrique_async(u: str | None = None) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(moteur_async(u), expire_on_commit=False)
