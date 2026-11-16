import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


class Base(DeclarativeBase):
    pass


_url = settings.database_url
_connect_args = {}
if _url.startswith("sqlite"):
    # Bundled SQLite file (flood.db): no database server needed.
    _connect_args["check_same_thread"] = False
    engine = create_engine(_url, connect_args=_connect_args)
else:
    # MySQL / TiDB / Aiven (optional). Set DB_SSL=true for cloud MySQL.
    if os.getenv("DB_SSL", "").lower() in ("1", "true", "yes"):
        import certifi
        _connect_args["ssl"] = {"ca": certifi.where()}
    engine = create_engine(_url, pool_pre_ping=True, pool_recycle=1800, connect_args=_connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
