import os
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

# Configurer les logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
DATA_SOURCE_ID = os.getenv("NOTION_DATA_SOURCE_ID")

# Initialisation du client
notion = Client(auth=NOTION_TOKEN, logger=logger)


def list_databases():
    """Récupère la liste des bases de données disponibles dans Notion et leurs identifiants."""
    try:
        logger.info("Récupération de la liste des bases de données Notion...")
        results = notion.search(
            filter={"value": "data_source", "property": "object"}
        ).get("results")

        databases = []
        for db in results:
            title_list = db.get("title", [])
            title = title_list[0].get("plain_text", "Sans titre") if title_list else "Sans titre"
            db_id = db.get("id")
            databases.append({title: db_id})

        logger.info(f"{len(databases)} base(s) de données trouvée(s).")
        return databases

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des bases de données : {e}")
        return []


def get_database_fields(database_id: str) -> dict:
    """
    Récupère la liste des champs (propriétés) disponibles dans une base de données Notion.

    :param database_id: L'identifiant de la base de données Notion.
    :return: Un dictionnaire avec les noms des champs comme clés et leurs types comme valeurs.
    """
    logger.info(f"Récupération des champs de la base de données : {database_id}")

    try:
        response = notion.databases.retrieve(database_id=database_id)
        properties = response.get("properties", {})

        fields = {
            name: prop["type"]
            for name, prop in properties.items()
        }

        logger.info(f"{len(fields)} champ(s) trouvé(s) : {list(fields.keys())}")
        return fields

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des champs : {e}")
        return {}


def get_data_source_fields(data_source_id: str) -> dict:
    """Recupère la liste des champs (propriétés) disponibles dans une data source Notion.

    :params data_source_id: L'identifiant de la data source Notion.
    :return: Un dictionnaire avec les noms des champs comme clés et leurs types comme valeurs.
    """
    logger.info(f"Récupération des champs de la data source...")
    try:
        response = notion.data_sources.retrieve(data_source_id=data_source_id)
        properties = response.get("properties", {})

        fields = {
            name: prop["type"]
            for name, prop in properties.items()
        }

        logger.info(f"{len(fields)} champ(s) trouvé(s) : {list(fields.keys())}")
        return fields

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des champs : {e}")
        return {}


def query_data_source(data_source_id: str, filter: dict = None, sorts: list = None) -> list:
    """Récupère les entrées d'une data source Notion avec pagination automatique.

    :param data_source_id: L'identifiant de la data source Notion.
    :param filter: Filtre optionnel sur les propriétés.
    :param sorts: Tri optionnel sur les propriétés.
    :return: Liste de toutes les entrées (pages) de la data source.
    """
    logger.info("Récupération des données de la data source...")

    results = []
    has_more = True
    next_cursor = None

    try:
        while has_more:
            params = {"data_source_id": data_source_id}
            if filter:
                params["filter"] = filter
            if sorts:
                params["sorts"] = sorts
            if next_cursor:
                params["start_cursor"] = next_cursor

            response = notion.data_sources.query(**params)

            results.extend(response.get("results", []))
            has_more = response.get("has_more", False)
            next_cursor = response.get("next_cursor")

            logger.info(f"{len(results)} entrée(s) récupérée(s) jusqu'ici...")

        logger.info(f"Terminé : {len(results)} entrée(s) au total.")
        return results

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des données : {e}")
        return []


def _extract_value(prop: dict):
    """Extrait la valeur brute d'une propriété Notion selon son type."""
    ptype = prop.get("type")
    if ptype == "title":
        items = prop.get("title", [])
        return items[0]["plain_text"] if items else None
    elif ptype == "rich_text":
        items = prop.get("rich_text", [])
        return items[0]["plain_text"] if items else None
    elif ptype == "number":
        return prop.get("number")
    elif ptype == "email":
        return prop.get("email")
    elif ptype == "select":
        sel = prop.get("select")
        return sel["name"] if sel else None
    elif ptype == "date":
        val = prop.get("date")
        return val["start"] if val else None
    elif ptype in ("last_edited_time", "created_time"):
        return prop.get(ptype)
    return None


def get_all_entries(data_source_id: str) -> list:
    """Récupère toutes les entrées de la data source avec pagination.

    :param data_source_id: L'identifiant de la data source Notion.
    :return: Liste de toutes les entrées.
    """
    logger.info("Récupération de toutes les entrées...")
    results = []
    has_more = True
    next_cursor = None

    try:
        while has_more:
            params = {"data_source_id": data_source_id}
            if next_cursor:
                params["start_cursor"] = next_cursor

            response = notion.data_sources.query(**params)
            results.extend(response.get("results", []))
            has_more = response.get("has_more", False)
            next_cursor = response.get("next_cursor")

        logger.info(f"{len(results)} entrée(s) récupérée(s).")
        return results

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des entrées : {e}")
        return []


def _compute_rankings(entries: list) -> dict[str, int]:
    """Calcule le classement de toutes les entrées.

    Critères : score croissant (bas = meilleur), puis date de soumission croissante.

    :param entries: Liste des entrées Notion.
    :return: Dictionnaire {page_id: rank}.
    """
    parsed = []
    for entry in entries:
        props = entry.get("properties", {})
        score = _extract_value(props.get("Score", {}))
        date_str = _extract_value(props.get("Submission Date", {}))

        # Entrées sans score classées en dernier
        score = score if score is not None else float("inf")
        date = datetime.fromisoformat(date_str) if date_str else datetime.max.replace(tzinfo=timezone.utc)

        parsed.append((entry["id"], score, date))

    # Tri : score croissant, puis date croissante
    parsed.sort(key=lambda x: (x[1], x[2]))

    return {page_id: rank + 1 for rank, (page_id, _, _) in enumerate(parsed)}


def upsert_submission(
    data_source_id: str,
    email: str,
    score: float,
    feasible_solutions: int,
    name: str = None,
) -> str:
    """Crée ou met à jour une soumission dans la data source Notion,
    puis recalcule le classement de toutes les entrées.

    :param data_source_id: L'identifiant de la data source Notion.
    :param email: Adresse e-mail du participant (clé d'identification).
    :param score: Score de la solution soumise.
    :param feasible_solutions: Nombre de solutions réalisables.
    :param name: Nom du participant (requis uniquement à la création).
    :return: L'ID de la page Notion créée ou mise à jour.
    """
    logger.info(f"Upsert de la soumission pour : {email}")

    # Déterminer le statut selon les solutions réalisables
    if feasible_solutions is None:
        status = "Null"
    elif feasible_solutions < 150:
        status = "Draft"
    else:
        status = "Complete"

    # Propriétés communes (create + update)
    properties = {
        "Email": {"email": email},
        "Score": {"number": score},
        "Feasible solutions": {"number": feasible_solutions},
        "Submission Status": {"select": {"name": status}},
    }

    try:
        existing_entries = get_all_entries(data_source_id)
        existing_page = None

        for entry in existing_entries:
            entry_email = _extract_value(entry["properties"].get("Email", {}))
            if entry_email == email:
                existing_page = entry
                break

        # Timestamp de soumission — géré manuellement
        submission_date = datetime.now(timezone.utc).isoformat()
        properties["Submission date"] = {
            "date": {"start": submission_date}
        }

        if existing_page:
            logger.info(f"Entrée existante trouvée ({existing_page['id']}), mise à jour...")
            if name is not None:
                properties["Name"] = {"rich_text": [{"text": {"content": name}}]}
            notion.pages.update(page_id=existing_page["id"], properties=properties)
            page_id = existing_page["id"]

        else:
            if name is None:
                raise ValueError(f"Le nom est requis pour créer une nouvelle soumission (email: {email})")
            logger.info("Aucune entrée existante, création d'une nouvelle page...")
            properties["Name"] = {"rich_text": [{"text": {"content": name}}]}
            database_id = (
                existing_entries[0]["parent"]["database_id"]
                if existing_entries
                else os.getenv("NOTION_DATABASE_ID")
            )
            response = notion.pages.create(
                parent={"database_id": database_id},
                properties=properties,
            )
            page_id = response["id"]

        # Recalculer les classements — ne mettre à jour que si le rang change
        logger.info("Recalcul des classements...")
        updated_entries = get_all_entries(data_source_id)
        rankings = _compute_rankings(updated_entries)

        for entry in updated_entries:
            pid = entry["id"]
            new_rank = rankings.get(pid)
            old_rank = _extract_value(entry["properties"].get("Rank", {}))
            if new_rank != old_rank:
                notion.pages.update(
                    page_id=pid,
                    properties={"Rank": {"number": new_rank}}
                )
                logger.info(f"Rang mis à jour : {pid} → {new_rank}")

        logger.info(f"Classements mis à jour.")
        return page_id

    except Exception as e:
        logger.error(f"Erreur lors de l'upsert : {e}")
        raise

def delete_submission(data_source_id: str, email: str) -> bool:
    """Supprime (archive) une soumission identifiée par l'adresse e-mail,
    puis recalcule le classement.

    :param data_source_id: L'identifiant de la data source Notion.
    :param email: Adresse e-mail du participant à supprimer.
    :return: True si supprimé, False si non trouvé.
    """
    logger.info(f"Suppression de la soumission pour : {email}")

    try:
        entries = get_all_entries(data_source_id)
        target_page_id = None

        for entry in entries:
            entry_email = _extract_value(entry["properties"].get("Email", {}))
            if entry_email == email:
                target_page_id = entry["id"]
                break

        if not target_page_id:
            logger.warning(f"Aucune soumission trouvée pour : {email}")
            return False

        # Archiver la page (suppression logique dans Notion)
        notion.pages.update(page_id=target_page_id, archived=True)
        logger.info(f"Soumission archivée : {target_page_id}")

        # Recalculer les classements
        updated_entries = get_all_entries(data_source_id)
        rankings = _compute_rankings(updated_entries)
        for pid, rank in rankings.items():
            notion.pages.update(page_id=pid, properties={"Rank": {"number": rank}})
        logger.info(f"Classements recalculés après suppression.")

        return True

    except Exception as e:
        logger.error(f"Erreur lors de la suppression : {e}")
        return False

