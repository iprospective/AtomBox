"""Alembic : l'URL vient de DATABASE_URL, le schéma vient du dictionnaire (F114)."""
import os
from alembic import context
from sqlalchemy import create_engine

def run():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL absent — ex. postgresql+psycopg://atombox@localhost/atombox")
    engine = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    with engine.connect() as cnx:
        context.configure(connection=cnx, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()

run()
