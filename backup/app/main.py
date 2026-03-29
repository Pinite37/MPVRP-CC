import os
import shutil
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backup.database.models_db as models
from backup.database.db import engine
from backup.app.routes import generator, model, scoring, scoreboard, auth

load_dotenv()
FRONTEND_PROD_URL = os.getenv("FRONTEND_PROD_URL", "")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000", "https://ifri-ai-classes.github.io", FRONTEND_PROD_URL]
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

