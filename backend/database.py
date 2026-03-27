"""Database initialization and session management."""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from backend.config import DATA_DIR, DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False)


def init_db() -> None:
    """Create all tables if they do not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    with Session(engine) as session:
        yield session
