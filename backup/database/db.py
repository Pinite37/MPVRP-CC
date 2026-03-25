import os
import logging
from urllib.parse import urlparse

from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)


def _resolve_database_url() -> str:
    """Resolve and validate DATABASE_URL with a safe local default."""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./mpvrp_scoring.db")
    parsed = urlparse(database_url)

    if not parsed.scheme:
        raise RuntimeError("DATABASE_URL must include a valid scheme (e.g., sqlite:///..., postgresql://...).")

    return database_url

SQLALCHEMY_DATABASE_URL = _resolve_database_url()
is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    logger.info("Using SQLite database at %s", SQLALCHEMY_DATABASE_URL)

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Create database tables based on SQLAlchemy models (call at startup)."""
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()