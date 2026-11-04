"""SQLAlchemy engine and session. SQLite by default, PostgreSQL through DATABASE_URL."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    kw: dict = {"future": True}
    if url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kw["poolclass"] = StaticPool
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    eng = create_engine(url, **kw)
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _fk(dbapi_con, _):  # enforce foreign keys on SQLite
            cur = dbapi_con.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return eng


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release. create_all() makes new tables but never alters old ones, so a database made by an
# earlier version gets these added here. Each statement is safe to run again.
_NEW_COLUMNS = [
    ("users", "email", "VARCHAR(120)"),
    ("users", "password_hash", "VARCHAR(200)"),
    ("users", "link_code", "VARCHAR(12)"),
    ("schools", "staff_code", "VARCHAR(20)"),
    ("schools", "created_at", "TIMESTAMP"),
]
_NEW_INDEXES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_role ON users (email, role)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_link_code ON users (link_code)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_schools_staff_code ON schools (staff_code)",
]


def ensure_schema() -> None:
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as con:
        for table, col, typ in _NEW_COLUMNS:
            if table in insp.get_table_names() and col not in {c["name"] for c in insp.get_columns(table)}:
                con.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
        for stmt in _NEW_INDEXES:
            con.execute(text(stmt))


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(engine)
    ensure_schema()
