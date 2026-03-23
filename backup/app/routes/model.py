import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile, File

from backup.core.model.feasibility import verify_solution
from backup.core.model.utils import parse_instance, parse_solution
from backup.app.schemas import SolutionVerificationResponse

router = APIRouter(prefix="/model", tags=["Model"])


@router.post("/verify", response_model=SolutionVerificationResponse)
async def verify_solution_endpoint(
    instance_file: UploadFile = File(..., description="Instance file (.dat)"),
    solution_file: UploadFile = File(..., description="Solution file (.dat)")
):
    """
    Checks the feasibility of a solution for a given MPVRP-CC instance.

    Performs the following checks:

    - Vehicle consistency (departure/arrival at the correct garage)
    - Compliance with truck capacities
    - Weight maintenance (quantity loaded = quantity delivered)
    - Meeting the demand of all stations
    - Compliance with depot stock levels
    - Metric validation

    Returns:

    - feasible: True if the solution is valid, False otherwise
    - errors: List of detected errors
    - metrics: Recalculated solution metrics
    """
    temp_instance_path = None
    temp_solution_path = None

    try:
        # Sauvegarder temporairement les fichiers uploadés
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.dat', delete=False) as tmp_instance:
            content = await instance_file.read()
            tmp_instance.write(content)
            temp_instance_path = tmp_instance.name

        with tempfile.NamedTemporaryFile(mode='wb', suffix='.dat', delete=False) as tmp_solution:
            content = await solution_file.read()
            tmp_solution.write(content)
            temp_solution_path = tmp_solution.name

        # Parser l'instance et la solution
        instance = parse_instance(temp_instance_path)
        solution = parse_solution(temp_solution_path)

        # Vérifier la solution
        errors, computed_metrics = verify_solution(instance, solution)

        return SolutionVerificationResponse(
            feasible=len(errors) == 0,
            errors=errors,
            metrics=computed_metrics
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error during verification: {str(e)}")

    finally:
        # Nettoyer les fichiers temporaires
        if temp_instance_path and os.path.exists(temp_instance_path):
            os.unlink(temp_instance_path)
        if temp_solution_path and os.path.exists(temp_solution_path):
            os.unlink(temp_solution_path)
