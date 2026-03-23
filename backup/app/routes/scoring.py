import json
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from backup.database.db import get_db, SessionLocal
from backup.database import models_db as models
from backup.core.scoring.score_evaluation import process_full_submission
from backup.core.auth.auth_logic import get_current_user
from backup.app.schemas import SubmissionResultResponse, TeamHistoryResponse

router = APIRouter(prefix="/scoring", tags=["Scoring"])


def run_scoring_in_background(submission_id: int, zip_path: str):
    """Worker avec sa propre session DB — indépendante de la session HTTP."""
    db = SessionLocal()
    try:
        process_full_submission(submission_id, zip_path, db)
    finally:
        db.close()


def serialize_datetime(dt) -> str:
    """
    Convertit un datetime Python ou une string SQLite en ISO 8601 avec T.
    SQLAlchemy + SQLite peut retourner soit un datetime, soit une string brute
    selon le driver: on normalise les deux cas ici.
    """
    if dt is None:
        return None
    if hasattr(dt, 'isoformat'): #objet datetime Python
        return dt.isoformat()
    return str(dt).replace(' ', 'T') #string SQLite "2026-03-23 10:00:00"


@router.post("/submit")
async def submit_solutions_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    user_id = current_user.id
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur/Équipe non trouvé.e")

    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Seuls les fichiers .zip sont acceptés")

    unique_filename = f"upload_{uuid.uuid4()}.zip"
    temp_path = os.path.join("temp", unique_filename)
    os.makedirs("temp", exist_ok=True)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde : {str(e)}")

    new_submission = models.Submission(
        user_id=user_id,
        total_weighted_score=0.0,
        is_fully_feasible=False
    )
    db.add(new_submission)
    db.commit()
    db.refresh(new_submission)

    background_tasks.add_task(run_scoring_in_background, new_submission.id, temp_path)

    return {
        "status": "Accepted",
        "submission_id": new_submission.id,
        "team": user.team_name,
        "message": "Le calcul de votre score a débuté. Les résultats seront bientôt disponibles sur le leaderboard."
    }


@router.get("/result/{submission_id}", response_model=SubmissionResultResponse)
async def get_submission_result(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Soumission non trouvée")

    if submission.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette soumission")

    db.refresh(submission)

    is_ready = submission.total_weighted_score is not None and submission.total_weighted_score > 0

    results = []
    if is_ready:
        results = db.query(models.InstanceResult).filter(
            models.InstanceResult.submission_id == submission_id
        ).all()

    detailed_results = [
        {
            "instance": r.instance_name,
            "category": r.category,
            "feasible": r.is_feasible,
            "distance": r.calculated_distance,
            "transition_cost": r.calculated_transition_cost,
            "errors": json.loads(r.errors_log) if r.errors_log else []
        }
        for r in results
    ]

    return {
        "submission_id": submission.id,
        "submitted_at": serialize_datetime(submission.submitted_at),
        "total_score": submission.total_weighted_score,
        "is_fully_feasible": submission.is_fully_feasible,
        "total_valid_instances": f"{submission.total_feasible_count}/150",
        "total_valid_instances_per_category": submission.category_stats,
        "is_ready": is_ready,
        "processor_info": submission.processor_info,
        "instances_details": detailed_results
    }


@router.get("/history", response_model=TeamHistoryResponse)
async def get_user_submission_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    submissions = (
        db.query(models.Submission)
        .filter(models.Submission.user_id == current_user.id)
        .order_by(models.Submission.submitted_at.asc())
        .all()
    )

    history = []
    for number, sub in enumerate(submissions, start=1):
        history.append({
            "submission_id": sub.id,
            # Numéro relatif à l'équipe : 1, 2, 3... peu importe l'id global
            "submission_number": number,
            "submitted_at": serialize_datetime(sub.submitted_at),
            "score": round(sub.total_weighted_score, 2),
            "valid_instances": f"{sub.total_feasible_count}/150",
            "is_fully_feasible": sub.is_fully_feasible
        })

    # Réordonne du plus récent au plus ancien pour l'affichage
    history.reverse()

    return {
        "team_name": user.team_name,
        "total_submissions": len(history),
        "history": history
    }