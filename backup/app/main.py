import os
import shutil
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backup.database.models_db as models
from backup.database.db import engine
from backup.app.routes import generator, model, scoring, scoreboard, auth

load_dotenv()
FRONTEND_DEV_URL = os.getenv("FRONTEND_DEV_URL", "")
FRONTEND_PROD_URL = os.getenv("FRONTEND_PROD_URL", "")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _normalize_origin(origin: str) -> str | None:
    """Normalize CORS entries to scheme://host[:port] and drop invalid values."""
    raw = origin.strip()
    if not raw:
        return None

    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        logger.warning("Ignoring invalid CORS origin '%s'", origin)
        return None

    normalized = f"{parsed.scheme}://{parsed.netloc}"
    if normalized != raw.rstrip("/"):
        logger.warning("Normalized CORS origin '%s' to '%s'", origin, normalized)
    return normalized


def _normalized_unique(origins: list[str]) -> list[str]:
    result: list[str] = []
    for origin in origins:
        normalized = _normalize_origin(origin)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _build_allowed_origins() -> list[str]:
    """Build a strict CORS allow-list from environment variables."""
    allowed_origins_env = os.getenv("FRONTEND_ALLOWED_ORIGINS", "")
    parsed = _normalized_unique(allowed_origins_env.split(","))

    if parsed:
        return parsed

    # Backward-compatible fallback when comma-separated variable is not set.
    legacy_origins = _normalized_unique([FRONTEND_DEV_URL, FRONTEND_PROD_URL])
    if legacy_origins:
        return legacy_origins

    # Safe local fallback for development/test only.
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


ALLOWED_ORIGINS = _build_allowed_origins()
logger.info("CORS allow-list configured with %s origin(s)", len(ALLOWED_ORIGINS))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Création des tables
    models.Base.metadata.create_all(bind=engine)

    # Nettoyage de temp/ au démarrage
    temp_dir = "temp"
    if os.path.exists(temp_dir):
        orphans = os.listdir(temp_dir)
        if orphans:
            logger.info("Startup cleanup: removing %s orphan file(s) in temp/", len(orphans))
            shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    yield  

app = FastAPI(
    title="MPVRP-CC API",
    description="API for generating instances and verifying solutions to the MPVRP-CC problem (Multi-Product Vehicle Routing Problem with Changeover Cost)",
    version="1.0.0",
    lifespan=lifespan
)

# Configuration CORS pour permettre les appels depuis n'importe quelle origine
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclure les routes
app.include_router(generator.router)
app.include_router(model.router)
app.include_router(scoring.router)
app.include_router(auth.router)
app.include_router(scoreboard.router)

@app.api_route("/", methods=["GET", "HEAD"], tags=["Root"])
async def root():
    """Point d'entrée de l'API"""
    return {
        "message": "Bienvenue sur l'API MPVRP-CC",
        "documentation": "/docs",
        "endpoints": {
            "generator": "/generator/generate - POST: Génère une instance MPVRP-CC",
            "model": "/model/verify - POST: Vérifie une solution pour une instance"
        }
    }


@app.api_route("/health", methods=["GET", "HEAD"], tags=["Health"], include_in_schema=False)
async def health_check():
    """Vérifie l'état de santé de l'API"""
    return {"status": "healthy"}

