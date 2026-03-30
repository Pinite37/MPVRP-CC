import os

from fastapi import APIRouter

from backup.database.notion import get_all_entries, _extract_value
from backup.app.schemas import LeaderboardEntry


router = APIRouter(prefix="/scoreboard", tags=["scoreboard"], include_in_schema=True)

DATA_SOURCE_ID = os.getenv("NOTION_DATA_SOURCE_ID")


@router.get("/", response_model=list[LeaderboardEntry])
async def get_global_leaderboard():
    """Retourne le leaderboard trié par rang depuis Notion."""
    entries = get_all_entries(DATA_SOURCE_ID)

    leaderboard = []
    for entry in entries:
        props = entry["properties"]
        rank = _extract_value(props.get("Rank", {}))
        if rank is None:
            continue
        leaderboard.append(LeaderboardEntry(
            rank=rank,
            name=_extract_value(props.get("Name", {})) or "—",
            email=_extract_value(props.get("Email", {})),
            score=round(_extract_value(props.get("Score", {})) or 0, 2),
            feasible_solutions=_extract_value(props.get("Feasible solutions", {})) or 0,
            status=_extract_value(props.get("Submission Status", {})),
            submitted_at=_extract_value(props.get("Submission date", {})),
        ))

    leaderboard.sort(key=lambda x: x.rank)
    return leaderboard