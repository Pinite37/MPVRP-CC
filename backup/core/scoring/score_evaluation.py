import os
import zipfile
import shutil
import json

from sqlalchemy.orm import Session

from backup.database import models_db as models
from backup.core.model.feasibility import verify_solution
from backup.core.model.utils import parse_instance, parse_solution

COEFFS = {"small": 1.0, "medium": 0.5, "large": 0.2}
BIG_M  = 100000.0
NUMBER_OF_INSTANCES_PER_CATEGORY = 50

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
INSTANCES_ROOT = os.path.join(BASE_DIR, "data", "instances")

# Nouvelles fonctions pour gérer les erreurs
def _mark_submission_failed(submission_id: int, reason: str, db: Session):
    """
    Erreur fatale (ZIP illisible, dossier Solutions/ absent...) :
    score pénalisé pour que is_ready devienne True côté frontend
    et que l'équipe voie un message d'erreur plutôt qu'un spinner infini.
    """
    try:
        sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
        if sub:
            sub.total_weighted_score = BIG_M * 150
            sub.is_fully_feasible    = False
            sub.total_feasible_count = 0
            sub.category_stats       = json.dumps({"small": 0, "medium": 0, "large": 0})
            sub.processor_info       = reason
            db.commit()
    except Exception as e:
        print(f"[WORKER {submission_id}] Impossible de marquer l'échec : {e}")


def _discover_category_dirs(extract_root: str) -> tuple[dict, list]:
    """
    Trouve les dossiers small/medium/large n'importe où dans l'arborescence du ZIP.
    Retourne le chemin retenu par catégorie + d'éventuels avertissements.
    """
    candidates = {"small": [], "medium": [], "large": []}

    for root, dirs, _ in os.walk(extract_root):
        for dirname in dirs:
            category = dirname.lower()
            if category in candidates:
                candidates[category].append(os.path.join(root, dirname))

    category_dirs = {}
    warnings = []

    for category, paths in candidates.items():
        if not paths:
            continue

        # Choix déterministe : dossier le plus proche de la racine, puis ordre alpha.
        sorted_paths = sorted(paths, key=lambda p: (p.count(os.sep), p.lower()))
        selected = sorted_paths[0]
        category_dirs[category] = selected

        if len(sorted_paths) > 1:
            rel_selected = os.path.relpath(selected, extract_root)
            warnings.append(
                f"Plusieurs dossiers pour '{category}' trouvés ; utilisation de '{rel_selected}'."
            )

    return category_dirs, warnings


def _parse_solution_filename(filename: str):
    """Retourne (category, instance_num) si le nom est reconnu, sinon None."""
    if not filename.lower().endswith(".dat"):
        return None

    stem = filename[:-4]
    parts = stem.split("_")
    if len(parts) < 3 or parts[0].lower() != "sol":
        return None

    # Format court : Sol_S_002.dat
    if parts[1].upper() in {"S", "M", "L"} and len(parts[2]) == 3 and parts[2].isdigit():
        category = {"S": "small", "M": "medium", "L": "large"}[parts[1].upper()]
        return category, parts[2]

    # Format long : Sol_MPVRP_S_002_*.dat (suffixe libre)
    if (
        len(parts) >= 4
        and parts[1].lower() == "mpvrp"
        and parts[2].upper() in {"S", "M", "L"}
        and len(parts[3]) == 3
        and parts[3].isdigit()
    ):
        category = {"S": "small", "M": "medium", "L": "large"}[parts[2].upper()]
        return category, parts[3]

    return None


def _index_category_solution_files(cat_path: str, category: str) -> dict:
    """Indexe les fichiers .dat d'une catégorie par numéro d'instance reconnu."""
    parsed_candidates = {}
    unexpected = []
    dat_files = [f for f in os.listdir(cat_path) if f.lower().endswith(".dat")]

    for filename in dat_files:
        parsed = _parse_solution_filename(filename)
        if parsed is None:
            unexpected.append(filename)
            continue

        parsed_category, instance_num = parsed
        if parsed_category != category:
            unexpected.append(filename)
            continue

        instance_idx = int(instance_num)
        if instance_idx < 1 or instance_idx > NUMBER_OF_INSTANCES_PER_CATEGORY:
            unexpected.append(filename)
            continue

        parsed_candidates.setdefault(instance_num, []).append(filename)

    files_by_instance = {}
    duplicates = {}
    for instance_num, names in parsed_candidates.items():
        sorted_names = sorted(names, key=lambda n: (len(n), n.lower()))
        files_by_instance[instance_num] = sorted_names[0]
        if len(sorted_names) > 1:
            duplicates[instance_num] = sorted_names[1:]

    return {
        "dat_count": len(dat_files),
        "files_by_instance": files_by_instance,
        "unexpected": sorted(unexpected),
        "duplicates": duplicates,
    }


def _validate_zip_structure(extract_root: str, category_dirs: dict, discovery_warnings=None) -> dict:
    """
    Pré-check de la structure du ZIP après extraction.
    Retourne un rapport avec :
      - ok        : bool — True si tout est conforme
      - warnings  : list[str] — anomalies non bloquantes
      - errors    : list[str] — anomalies bloquantes par catégorie
      - by_category : dict — état détaillé par catégorie
    """
    report = {
        "ok": True,
        "warnings": list(discovery_warnings or []),
        "errors": [],
        "by_category": {}
    }

    prefix_map = {"small": "S", "medium": "M", "large": "L"}

    for category, prefix in prefix_map.items():
        cat_report = {
            "present": False,
            "dat_count": 0,
            "missing": [],
            "unexpected": [],
            "duplicates": {},
            "files_by_instance": {},
        }
        cat_path = category_dirs.get(category)

        if cat_path is None:
            cat_report["present"] = False
            report["errors"].append(
                f"Dossier '{category}' absent (recherche insensible à la casse) — "
                f"les 50 instances {category} recevront la pénalité maximale."
            )
            report["ok"] = False
        else:
            cat_report["present"] = True
            category_index = _index_category_solution_files(cat_path, category)
            cat_report["dat_count"] = category_index["dat_count"]
            cat_report["unexpected"] = category_index["unexpected"]
            cat_report["duplicates"] = category_index["duplicates"]
            cat_report["files_by_instance"] = category_index["files_by_instance"]

            expected_ids = {f"{i:03d}" for i in range(1, NUMBER_OF_INSTANCES_PER_CATEGORY + 1)}
            found_ids = set(category_index["files_by_instance"].keys())
            missing = sorted(expected_ids - found_ids)
            cat_report["missing"] = missing

            if (
                category_index["dat_count"] != NUMBER_OF_INSTANCES_PER_CATEGORY
                or missing
                or category_index["unexpected"]
                or category_index["duplicates"]
            ):
                cat_display = os.path.relpath(cat_path, extract_root)
                msg = (
                    f"{cat_display} : {category_index['dat_count']} fichier(s) .dat, "
                    f"{len(found_ids)} instance(s) reconnue(s) sur {NUMBER_OF_INSTANCES_PER_CATEGORY}."
                )
                if missing:
                    msg += f" Manquants : {', '.join(f'Sol_{prefix}_{m}.dat' for m in missing[:5])}"
                    if len(missing) > 5:
                        msg += f" … (+{len(missing) - 5})"
                if category_index["unexpected"]:
                    msg += f" Noms non reconnus : {', '.join(category_index['unexpected'][:3])}"
                    if len(category_index["unexpected"]) > 3:
                        msg += f" … (+{len(category_index['unexpected']) - 3})"
                if category_index["duplicates"]:
                    dup_count = sum(len(v) for v in category_index["duplicates"].values())
                    msg += f" Doublons ignorés : {dup_count}."
                report["warnings"].append(msg)

        report["by_category"][category] = cat_report

    return report


def _format_processor_info(report: dict) -> str:
    """Sérialise le rapport de structure en string lisible pour processor_info."""
    lines = ["=== Rapport de structure du ZIP ==="]

    if report["ok"] and not report["warnings"]:
        lines.append("Structure conforme — 3 catégories présentes, 50 fichiers chacune.")
        return "\n".join(lines)

    if report["errors"]:
        lines.append("\nERREURS BLOQUANTES :")
        for e in report["errors"]:
            lines.append(f"  • {e}")

    if report["warnings"]:
        lines.append("\nAVERTISSEMENTS :")
        for w in report["warnings"]:
            lines.append(f"  • {w}")

    lines.append("\n--- Détail par catégorie ---")
    for cat, info in report["by_category"].items():
        status = "✅" if info["present"] and info["dat_count"] == NUMBER_OF_INSTANCES_PER_CATEGORY else "❌"
        lines.append(f"  {status} {cat.capitalize()} : {info['dat_count']}/{NUMBER_OF_INSTANCES_PER_CATEGORY} fichiers")

    return "\n".join(lines)


def process_full_submission(submission_id: int, zip_path: str, db: Session):
    extract_path = f"temp_extract_{submission_id}"
    total_valid_instances = 0
    results_per_category  = {"small": 0, "medium": 0, "large": 0}

    try:
        # Vérification existence du ZIP 
        if not os.path.exists(zip_path):
            _mark_submission_failed(submission_id, f"Fichier ZIP introuvable : {zip_path}", db)
            return

        # Extraction
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
        except zipfile.BadZipFile:
            _mark_submission_failed(submission_id, "Le fichier soumis n'est pas un ZIP valide.", db)
            return
        except Exception as e:
            _mark_submission_failed(submission_id, f"Erreur lors de l'extraction : {e}", db)
            return

        category_dirs, discovery_warnings = _discover_category_dirs(extract_path)

        # Pré-check structure détaillé
        structure_report = _validate_zip_structure(extract_path, category_dirs, discovery_warnings)
        processor_info   = _format_processor_info(structure_report)

        # On met à jour processor_info dès maintenant (avant la boucle)
        sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
        if sub:
            sub.processor_info = processor_info
            db.commit()

        # Boucle d'évaluation 
        total_weighted_sum = 0
        fully_feasible     = True

        for category, weight in COEFFS.items():
            category_score = 0
            instance_dir   = os.path.join(INSTANCES_ROOT, category)
            cat_info       = structure_report["by_category"].get(category, {})
            category_path  = category_dirs.get(category)
            files_by_instance = cat_info.get("files_by_instance", {})

            instance_mapping = {}
            if os.path.exists(instance_dir):
                for f in os.listdir(instance_dir):
                    if f.startswith("MPVRP_") and (f.endswith(".txt") or f.endswith(".dat")):
                        parts = f.split('_')
                        if len(parts) >= 3:
                            instance_mapping[parts[2]] = f

            for i in range(1, NUMBER_OF_INSTANCES_PER_CATEGORY + 1):
                num_str   = f"{i:03d}"
                prefix    = category[0].upper()
                sol_name  = f"Sol_{prefix}_{num_str}.dat"
                errors    = []
                metrics   = {}
                feasible  = False

                if not cat_info.get("present", False):
                    # Erreur déjà signalée dans processor_info
                    errors = [f"Catégorie {category} absente du ZIP (voir rapport de structure)."]

                else:
                    selected_solution = files_by_instance.get(num_str)
                    sol_path = os.path.join(str(category_path), selected_solution) if category_path and selected_solution else None
                    inst_filename = instance_mapping.get(num_str)
                    inst_path     = os.path.join(instance_dir, inst_filename) if inst_filename else None

                    if not inst_filename:
                        errors = [f"Instance officielle {num_str} introuvable sur le serveur."]
                    elif not sol_path or not os.path.exists(sol_path):
                        errors = [
                            f"Aucun fichier solution valide trouvé pour l'instance {num_str} "
                            f"dans la catégorie '{category}'."
                        ]
                    else:
                        try:
                            instance_obj = parse_instance(inst_path)
                            solution_obj = parse_solution(str(sol_path))
                            errors, metrics = verify_solution(instance_obj, solution_obj)
                            feasible = (len(errors) == 0)
                            if feasible:
                                total_valid_instances += 1
                                results_per_category[category] += 1
                        except Exception as e:
                            errors = [f"Erreur technique lors du parsing : {e}"]

                instance_score = (
                    metrics.get("distance_total", 0) + metrics.get("total_switch_cost", 0)
                    if feasible else BIG_M
                )
                if not feasible:
                    fully_feasible = False

                category_score += instance_score

                db.add(models.InstanceResult(
                    submission_id              = submission_id,
                    category                   = category,
                    instance_name              = sol_name,
                    is_feasible                = feasible,
                    calculated_distance        = metrics.get("distance_total", 0),
                    calculated_transition_cost = metrics.get("total_switch_cost", 0),
                    errors_log                 = json.dumps(errors)
                ))

            total_weighted_sum += category_score * weight

        #Mise à jour finale
        sub = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
        if sub:
            sub.total_weighted_score = total_weighted_sum / 3
            sub.is_fully_feasible    = fully_feasible
            sub.total_feasible_count = total_valid_instances
            sub.category_stats       = json.dumps(results_per_category)
            db.commit()

    except Exception as fatal_e:
        _mark_submission_failed(submission_id, f"Erreur inattendue : {fatal_e}", db)

    finally:
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)

        if os.path.exists(zip_path):
            os.remove(zip_path)