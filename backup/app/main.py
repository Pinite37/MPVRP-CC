import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backup.database.models_db as models
from backup.database.db import engine
from backup.app.routes import generator, model, scoring, scoreboard, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Création des tables
    models.Base.metadata.create_all(bind=engine)

    # Nettoyage de temp/ au démarrage
    temp_dir = "temp"
    if os.path.exists(temp_dir):
        orphans = os.listdir(temp_dir)
        if orphans:
            print(f"[STARTUP] Nettoyage de {len(orphans)} fichier(s) orphelin(s) dans temp/")
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
    allow_origins=["*"],
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
            "model": "/model/verify - POST: Vérifie une solution pour une instance",
            "scoring_1": "/scoring/submit/{user_id} - POST: Evalue la faisabilité des 150 solutions",
            "scoring_2": "/scoring/result/{submission_id} - GET: Retourne les résultats détaillés de l'évaluation de la soumission",
            "scoring_3": "scoring/history/{user_id} - GET: Retourne l'historique des soumissions de l'utilisateur",
            "scoreboard": "/scoreboard/ - GET: Renvoie le classement officiel avec la meilleure soumission par équipe"
        }
    }


@app.api_route("/health", methods=["GET", "HEAD"], tags=["Health"])
async def health_check():
    """Vérifie l'état de santé de l'API"""
    return {"status": "healthy"}

