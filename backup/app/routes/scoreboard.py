from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backup.database.db import get_db
from backup.database import models_db as models
from backup.app.schemas import LeaderboardEntry

router = APIRouter(prefix="/scoreboard", tags=["scoreboard"])

@router.get("/", response_model=list[LeaderboardEntry])
async def get_global_leaderboard(db: Session = Depends(get_db)):
    """
    Retourne le leaderboard officiel : meilleure soumission par équipe.
    
    FIX : la jointure se fait sur submission.id (et non sur le score),
    ce qui évite les doublons quand plusieurs soumissions ont le même score
    """
    # 1/ pour chaque équipe, trouver l'id de sa meilleure soumission
    #en gardant la soumission la plus récente (submitted_at le plus grand)
    best_subquery = (
        db.query(
            models.Submission.user_id,
            func.min(models.Submission.total_weighted_score).label("min_score")
        )
        .group_by(models.Submission.user_id)
        .subquery()
    )

    # 2/ parmi les soumissions au score minimal, garder la plus récente
    best_id_subquery = (
        db.query(
            func.max(models.Submission.id).label("best_id")
        )
        .join(
            best_subquery,
            (models.Submission.user_id == best_subquery.c.user_id) &
            (models.Submission.total_weighted_score == best_subquery.c.min_score)
        )
        .group_by(models.Submission.user_id)
        .subquery()
    )

    # 3/récupérer les données complètes pour ces soumissions uniquement
    query = (
        db.query(
            models.User.team_name,
            models.Submission.id,
            models.Submission.total_weighted_score,
            models.Submission.total_feasible_count,
            models.Submission.submitted_at
        )
        .join(best_id_subquery, models.Submission.id == best_id_subquery.c.best_id)
        .join(models.User, models.User.id == models.Submission.user_id)
        .order_by(models.Submission.total_weighted_score.asc())
        .all()
    )

    leaderboard = []
    for i, row in enumerate(query):
        leaderboard.append({
            "rank": i + 1,
            "team": row.team_name,
            "score": round(row.total_weighted_score, 2),
            "instances_validated": f"{row.total_feasible_count}/150",
            # FIX DATE : .isoformat() pour cohérence avec scoring router
            "last_submission": row.submitted_at.isoformat()
        })

    return leaderboard