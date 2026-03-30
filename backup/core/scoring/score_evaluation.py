import os
import zipfile
import shutil
import logging

from .utils import _discover_category_dirs, _validate_zip_structure, _format_processor_info, _failed_result


COEFFS = {"small": 1.0, "medium": 0.5, "large": 0.2}
BIG_M = 100000.0
NUMBER_OF_INSTANCES_PER_CATEGORY = 50

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
INSTANCES_ROOT = os.path.join(BASE_DIR, "data", "instances")


def process_full_submission(zip_path: str) -> dict:
    """Evaluates a ZIP submission and returns a results dictionary.

    :param zip_path: Path to the submitted ZIP file.
    :return: Dictionary with score, feasibility, and details per instance.
    """
    extract_path = f"temp_extract_{os.path.basename(zip_path)}"
    total_valid_instances = 0
    results_per_category = {"small": 0, "medium": 0, "large": 0}
    instance_results = []

    try:
        if not os.path.exists(zip_path):
            return _failed_result(f"ZIP file not found: {zip_path}")

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
        except zipfile.BadZipFile:
            return _failed_result("The submitted file is not a valid ZIP file.")
        except Exception as e:
            return _failed_result(f"Error during extraction: {e}")

        category_dirs, discovery_warnings = _discover_category_dirs(extract_path)
        structure_report = _validate_zip_structure(extract_path, category_dirs, discovery_warnings)
        processor_info = _format_processor_info(structure_report)

        total_weighted_sum = 0
        fully_feasible = True

        for category, weight in COEFFS.items():
            category_score = 0
            instance_dir = os.path.join(INSTANCES_ROOT, category)
            cat_info = structure_report["by_category"].get(category, {})
            category_path = category_dirs.get(category)
            files_by_instance = cat_info.get("files_by_instance", {})

            instance_mapping = {}
            if os.path.exists(instance_dir):
                for f in os.listdir(instance_dir):
                    if f.startswith("MPVRP_") and (f.endswith(".txt") or f.endswith(".dat")):
                        parts = f.split('_')
                        if len(parts) >= 3:
                            instance_mapping[parts[2]] = f

            for i in range(1, NUMBER_OF_INSTANCES_PER_CATEGORY + 1):
                num_str = f"{i:03d}"
                prefix = category[0].upper()
                sol_name = f"Sol_{prefix}_{num_str}.dat"
                errors = []
                metrics = {}
                feasible = False

                if not cat_info.get("present", False):
                    errors = [f"Category {category} missing from ZIP."]
                else:
                    selected_solution = files_by_instance.get(num_str)
                    sol_path = os.path.join(str(category_path), selected_solution) if category_path and selected_solution else None
                    inst_filename = instance_mapping.get(num_str)
                    inst_path = os.path.join(instance_dir, inst_filename) if inst_filename else None

                    if not inst_filename:
                        errors = [f"Official instance {num_str} not found on server."]
                    elif not sol_path or not os.path.exists(sol_path):
                        errors = [f"No valid solution file found for instance {num_str}."]
                    else:
                        try:
                            from backup.core.model.feasibility import verify_solution
                            from backup.core.model.utils import parse_instance, parse_solution
                            instance_obj = parse_instance(inst_path)
                            solution_obj = parse_solution(str(sol_path))
                            errors, metrics = verify_solution(instance_obj, solution_obj)
                            feasible = (len(errors) == 0)
                            if feasible:
                                total_valid_instances += 1
                                results_per_category[category] += 1
                        except Exception as e:
                            errors = [f"Technical error during parsing: {e}"]

                instance_score = (
                    metrics.get("distance_total", 0) + metrics.get("total_switch_cost", 0)
                    if feasible else BIG_M
                )
                if not feasible:
                    fully_feasible = False

                category_score += instance_score
                instance_results.append({
                    "instance": sol_name,
                    "category": category,
                    "feasible": feasible,
                    "distance": metrics.get("distance_total", 0),
                    "transition_cost": metrics.get("total_switch_cost", 0),
                    "errors": errors,
                })

            total_weighted_sum += category_score * weight

        return {
            "ok": True,
            "total_weighted_score": total_weighted_sum / 3,
            "is_fully_feasible": fully_feasible,
            "total_feasible_count": total_valid_instances,
            "category_stats": results_per_category,
            "processor_info": processor_info,
            "instance_results": instance_results,
        }

    except Exception as fatal_e:
        return _failed_result(f"Unexpected error: {fatal_e}")

    finally:
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        if os.path.exists(zip_path):
            os.remove(zip_path)

