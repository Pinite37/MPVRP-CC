import os
import logging

COEFFS = {"small": 1.0, "medium": 0.5, "large": 0.2}
BIG_M = 100000.0
NUMBER_OF_INSTANCES_PER_CATEGORY = 50

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
INSTANCES_ROOT = os.path.join(BASE_DIR, "data", "instances")


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



def _failed_result(reason: str) -> dict:
    """Retourne un résultat d'échec standardisé."""
    return {
        "ok": False,
        "total_weighted_score": BIG_M * 150,
        "is_fully_feasible": False,
        "total_feasible_count": 0,
        "category_stats": {"small": 0, "medium": 0, "large": 0},
        "processor_info": reason,
        "instance_results": [],
    }