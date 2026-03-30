from typing import Optional

from pydantic import BaseModel, Field


class InstanceGenerationRequest(BaseModel):
    """Parameters for generating an MPVRP-CC instance"""
    id_instance: str = Field(..., description="Instance identifier (e.g., '01')")
    nb_vehicules: int = Field(..., ge=1, description="Number of vehicles")
    nb_depots: int = Field(..., ge=1, description="Number of depots")
    nb_garages: int = Field(..., ge=1, description="Number of garages")
    nb_stations: int = Field(..., ge=1, description="Number of stations")
    nb_produits: int = Field(..., ge=1, description="Number of products")
    max_coord: float = Field(default=100.0, description="Grid size")
    min_capacite: int = Field(default=10000, description="Minimum vehicle capacity")
    max_capacite: int = Field(default=25000, description="Maximum vehicle capacity")
    min_transition_cost: float = Field(default=10.0, description="Minimum product changeover cost")
    max_transition_cost: float = Field(default=80.0, description="Maximum product changeover cost")
    min_demand: int = Field(default=500, description="Minimum demand per station/product")
    max_demand: int = Field(default=5000, description="Maximum demand per station/product")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")


class InstanceGenerationResponse(BaseModel):
    filename: str
    content: str


class SolutionVerificationResponse(BaseModel):
    feasible: bool
    errors: list[str]
    metrics: dict



#SCORING & RESULTS
class InstanceDetail(BaseModel):
    instance: str
    category: str
    feasible: bool
    distance: float
    transition_cost: float
    errors: list[str]

class SubmissionResultResponse(BaseModel):
    submission_id: int
    submitted_at: str
    total_score: float
    is_fully_feasible: bool
    total_valid_instances: str
    total_valid_instances_per_category: Optional[str] = None
    is_ready: bool
    processor_info: Optional[str] = None
    instances_details: list[InstanceDetail]

    class Config:
        from_attributes = True


class LeaderboardEntry(BaseModel):
    rank: int
    team: str
    score: float
    instances_validated: str
    last_submission: Optional[str] = None

