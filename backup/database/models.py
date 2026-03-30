from typing import Optional

from pydantic import BaseModel


class InstanceResultSchema(BaseModel):
    instance: str
    category: str
    feasible: bool
    distance: float
    transition_cost: float
    errors: list[str]


class SubmissionResultSchema(BaseModel):
    submission_id: str
    submitted_at: Optional[str]
    total_score: float
    is_fully_feasible: bool
    total_valid_instances: str
    total_valid_instances_per_category: Optional[str]
    is_ready: bool
    processor_info: Optional[str]
    instances_details: list[InstanceResultSchema]


class LeaderboardEntry(BaseModel):
    rank: int
    name: str
    email: Optional[str]
    score: float
    feasible_solutions: int
    status: Optional[str]
    submitted_at: Optional[str]