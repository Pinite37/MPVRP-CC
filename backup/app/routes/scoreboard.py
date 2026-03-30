import os

from fastapi import APIRouter, HTTPException

from backup.database.notion import get_all_entries, _extract_value
from backup.app.schemas import LeaderboardEntry


router = APIRouter(prefix="/scoreboard", tags=["scoreboard"], include_in_schema=False)

DATA_SOURCE_ID = os.getenv("NOTION_DATA_SOURCE_ID")


@router.get("", response_model=list[LeaderboardEntry])
async def get_global_leaderboard():
    """Retourne le leaderboard trié par rang depuis Notion."""
    if not DATA_SOURCE_ID:
        raise HTTPException(status_code=500, detail="NOTION_DATA_SOURCE_ID is not configured")

    entries = get_all_entries(DATA_SOURCE_ID)

    leaderboard = []
    for entry in entries:
        props = entry["properties"]
        rank = _extract_value(props.get("Rank", {}))
        if rank is None:
            continue

        team = _extract_value(props.get("Name", {})) or _extract_value(props.get("Email", {})) or "—"
        feasible = _extract_value(props.get("Feasible solutions", {})) or 0
        submitted_at = _extract_value(props.get("Submission date", {})) or "—"

        leaderboard.append(LeaderboardEntry(
            rank=int(rank),
            team=team,
            score=round(_extract_value(props.get("Score", {})) or 0, 2),
            instances_validated=f"{int(feasible)}/150",
            last_submission=submitted_at,
        ))

    leaderboard.sort(key=lambda x: x.rank)
    return leaderboard