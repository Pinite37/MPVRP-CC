import json
import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form

from backup.core.scoring.score_evaluation import process_full_submission
from backup.database.notion import upsert_submission
from backup.app.schemas import SubmissionResultResponse

router = APIRouter(prefix="/scoring", tags=["Scoring"], include_in_schema=True)

DATA_SOURCE_ID = os.getenv("NOTION_DATA_SOURCE_ID")


@router.post("/submit", response_model=SubmissionResultResponse)
async def submit_solutions_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    email: str = Form(...),
    name: Optional[str] = Form(None),
):
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

    # Évaluation synchrone — le résultat est retourné directement
    result = process_full_submission(temp_path)

    # Upsert vers Notion en arrière-plan (non bloquant pour l'utilisateur)
    background_tasks.add_task(
        upsert_submission,
        data_source_id=DATA_SOURCE_ID,
        email=email,
        score=result["total_weighted_score"],
        feasible_solutions=result["total_feasible_count"],
        name=name,
    )

    return {
        "status": "Complete",
        "team": name or email,
        "total_score": round(result["total_weighted_score"], 2),
        "is_fully_feasible": result["is_fully_feasible"],
        "total_valid_instances": f"{result['total_feasible_count']}/150",
        "total_valid_instances_per_category": json.dumps(result["category_stats"]),
        "is_ready": True,
        "processor_info": result["processor_info"],
        "instances_details": result["instance_results"],
    }