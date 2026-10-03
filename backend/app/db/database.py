"""SQLAlchemy 2.x database engine, session factory, and declarative Base for D-DATO."""

from pathlib import Path
from typing import Generator, Optional
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.x declarative Base for all D-DATO ORM entities."""
    pass


def get_engine_args(url: str) -> dict:
    """Return appropriate engine arguments for the given database dialect."""
    args = {}
    if url.startswith("sqlite"):
        args["connect_args"] = {"check_same_thread": False}
    return args


# Application-level engine configured from settings
engine: Engine = create_engine(
    settings.DATABASE_URL,
    **get_engine_args(settings.DATABASE_URL),
)

# Request/task scoped session factory
SessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine: Optional[Engine] = None) -> None:
    """Initialize database schema by creating all tables defined in Base metadata."""
    eng = target_engine or engine
    if str(eng.url).startswith("sqlite"):
        db_file = eng.url.database
        if db_file and db_file != ":memory:":
            Path(db_file).resolve().parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=eng)


def reset_db(target_engine: Optional[Engine] = None) -> None:
    """Drop all tables defined in Base metadata (primarily for isolated test teardown)."""
    eng = target_engine or engine
    Base.metadata.drop_all(bind=eng)
