"""Database initialization and session management."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine

from backend.config import DATA_DIR, DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False)


def _sqlite_column_names(table_name: str) -> set[str]:
    with engine.connect() as connection:
        rows = connection.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
    return {str(row[1]) for row in rows}


def _run_sqlite_migrations() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "studentexamsheet" in table_names:
        columns = _sqlite_column_names("studentexamsheet")
        statements: list[str] = []

        if "page_summaries_json" not in columns:
            statements.append(
                "ALTER TABLE studentexamsheet ADD COLUMN page_summaries_json TEXT NOT NULL DEFAULT '[]'"
            )

        if statements:
            with engine.begin() as connection:
                for statement in statements:
                    connection.exec_driver_sql(statement)


def init_db() -> None:
    """Create all tables if they do not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    if DATABASE_URL.startswith("sqlite"):
        _run_sqlite_migrations()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    with Session(engine) as session:
        yield session
