"""La base : psycopg 3, SQL direct — le schéma vient du dictionnaire, pas d'un ORM (D154)."""
import os, psycopg
from psycopg.rows import dict_row

def url() -> str:
    u = os.environ.get("DATABASE_URL")
    if not u: raise SystemExit("DATABASE_URL absent — ex. postgresql:///atombox")
    return u

def connecter(u: str | None = None) -> psycopg.Connection:
    return psycopg.connect(u or url(), row_factory=dict_row)
