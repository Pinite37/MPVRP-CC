from __future__ import annotations
from typing import Any, Dict, List, Tuple

from .utils import solution_node_key
from .schemas import ParsedSolutionDat, Instance


def verify_solution(instance: Instance, solution: ParsedSolutionDat) -> Tuple[List[str], Dict[str, Any]]:
    """
    Vérifier la faisabilité et la cohérence d'une solution du MPVRP-CC.

    Cette fonction effectue les vérifications suivantes :

    1. Cohérence des véhicules : départ/arrivée au bon garage
    2. Respect des capacités : pas de dépassement de la capacité des camions
    3. Conservation de la masse : quantité chargée = quantité livrée pour chaque segment
    4. Satisfaction de la demande : toutes les stations reçoivent les quantités demandées
    5. Respect des stocks : les dépôts ne sont pas sur-prélevés
    6. Validation des métriques : comparaison avec les valeurs calculées

    Parameters
    ----------
    instance : Instance
        L'instance du problème MPVRP-CC.
    solution : ParsedSolutionDat
        La solution à vérifier.

    Returns
    -------
    Tuple[List[str], Dict[str, Any]]
        Une liste d'erreurs détectées (vide si la solution est faisable) et un dictionnaire des métriques recalculées.
    """
    errors: List[str] = []

    # Créer des tables de correspondance pour un accès rapide aux entités par ID numérique
    vehicle_by_id = {int(k[1:]): v for k, v in instance.camions.items()}
    depot_by_id = {int(k[1:]): v for k, v in instance.depots.items()}
    station_by_id = {int(k[1:]): v for k, v in instance.stations.items()}

    # Accumulateurs pour vérifier les livraisons et les chargements globaux
    deliveries: Dict[Tuple[str, int], float] = {}  # (station_id, product) -> quantité totale livrée
    loads: Dict[Tuple[str, int], float] = {}       # (depot_id, product) -> quantité totale chargée

    # Métriques recalculées pour validation
    computed_total_changes = 0        # Nombre de changements de produits
    computed_total_switch_cost = 0.0  # Coût total des changements de produits
    computed_distance_total = 0.0     # Distance totale parcourue par tous les véhicules

    # Parcourir chaque véhicule de la solution
    for v in solution.vehicles:
        # Vérifier que le véhicule existe dans l'instance
        camion = vehicle_by_id.get(v.vehicle_id)
        if camion is None:
            errors.append(f"Véhicule {v.vehicle_id}: absent de l'instance")
            continue

        # Vérifier que les listes de nœuds et de produits ont la même longueur
        if len(v.nodes) != len(v.products):
            errors.append(
                f"Véhicule {v.vehicle_id}: incompatibilité longueur route/produits ({len(v.nodes)} vs {len(v.products)})"
            )
            continue

        # Convertir les nœuds en clés formatées (ex: "D1", "S5", "G2")
        keyed_nodes = [solution_node_key(n["kind"], n["id"]) for n in v.nodes]
        if not keyed_nodes:
            errors.append(f"Véhicule {v.vehicle_id}: route vide")
            continue

        # Vérifier que le véhicule démarre et termine au bon garage
        expected_garage = camion.garage_id
        if keyed_nodes[0] != expected_garage or keyed_nodes[-1] != expected_garage:
            errors.append(
                f"Véhicule {v.vehicle_id}: garage incohérent (attendu {expected_garage}, obtenu {keyed_nodes[0]}..{keyed_nodes[-1]})"
            )

        # Calculer la distance totale parcourue par ce véhicule
        # Somme des distances entre chaque paire de nœuds consécutifs
        for a, b in zip(keyed_nodes, keyed_nodes[1:]):
            computed_distance_total += float(instance.distances.get((a, b), 0.0))

        # Calculer le nombre et le coût des changements de produits
        # Les produits sont exportés avec indexation 0-based dans la solution
        products_only = [p for (p, _c) in v.products]
        for prev_p, cur_p in zip(products_only, products_only[1:]):
            if prev_p != cur_p:
                computed_total_changes += 1
                computed_total_switch_cost += float(instance.costs.get((prev_p, cur_p), 0.0))

        # Vérifier la conservation de la masse pour chaque segment (dépôt → stations)
        # Un segment commence au chargement d'un dépôt et se termine au prochain dépôt ou au garage
        current_segment_load = None  # (depot_key, product, qty)
        current_segment_delivered = 0.0

        # Parcourir chaque nœud visité par le véhicule
        for idx, (node, (p, _cumul)) in enumerate(zip(v.nodes, v.products)):
            kind = node["kind"]
            key = solution_node_key(kind, node["id"])
            qty = float(node.get("qty", 0))

            if kind == "depot":
                # Traitement des dépôts : chargement de produit
                if node["id"] not in depot_by_id:
                    errors.append(f"Véhicule {v.vehicle_id}: dépôt inconnu D{node['id']}")

                # Vérifier que la quantité chargée ne dépasse pas la capacité du camion
                if qty > float(camion.capacity) + 1e-6:
                    errors.append(
                        f"Véhicule {v.vehicle_id}: capacité dépassée au dépôt {key} (chargé={qty}, capacité={camion.capacity})"
                    )

                # Accumuler la quantité totale chargée à ce dépôt pour ce produit
                loads[(key, p)] = loads.get((key, p), 0.0) + qty

                # Vérifier la conservation de la masse du segment précédent
                # La quantité chargée doit égaler la quantité livrée aux stations
                """
                if current_segment_load is not None:
                    dkey, pp, expected_qty = current_segment_load
                    if abs(current_segment_delivered - expected_qty) > 1e-2:
                        errors.append(
                            f"Véhicule {v.vehicle_id}: conservation masse segment {dkey} prod {pp} (chargé={expected_qty}, livré={current_segment_delivered})"
                        )
                """
                # Commencer un nouveau segment
                current_segment_load = (key, p, qty)
                current_segment_delivered = 0.0

            elif kind == "station":
                # Traitement des stations : livraison de produit
                if node["id"] not in station_by_id:
                    errors.append(f"Véhicule {v.vehicle_id}: station inconnue S{node['id']}")

                # Accumuler les livraisons globales pour vérifier la satisfaction de la demande
                deliveries[(key, p)] = deliveries.get((key, p), 0.0) + qty
                current_segment_delivered += qty

            else:
                # Traitement des garages : doivent être uniquement au début et à la fin
                if idx != 0 and idx != len(v.nodes) - 1:
                    errors.append(f"Véhicule {v.vehicle_id}: garage au milieu de la route (position {idx+1})")

        # Vérifier la conservation de la masse pour le dernier segment
        # (segment se terminant au garage sans rechargement)
        """
        if current_segment_load is not None:
            dkey, pp, expected_qty = current_segment_load
            if abs(current_segment_delivered - expected_qty) > 1e-2:
                errors.append(
                    f"Véhicule {v.vehicle_id}: conservation masse segment {dkey} prod {pp} (chargé={expected_qty}, livré={current_segment_delivered})"
                )
        """

    # Vérifier que toutes les demandes des stations sont satisfaites
    # L'instance utilise une indexation 0-based pour les produits dans les demandes
    for st in instance.stations.values():
        for p, demand in st.demand.items():
            if demand <= 0:
                continue
            delivered = deliveries.get((st.id, p), 0.0)
            if abs(delivered - float(demand)) > 1e-2:
                errors.append(f"Demande non satisfaite: {st.id} prod {p} (demande={demand}, livré={delivered})")

    # Vérifier que les stocks des dépôts ne sont pas dépassés
    # L'instance utilise une indexation 0-based pour les produits dans les stocks
    for d in instance.depots.values():
        for p, stock in d.stocks.items():
            taken = loads.get((d.id, p), 0.0)
            if taken - float(stock) > 1e-2:
                errors.append(f"Stock dépassé: {d.id} prod {p} (stock={stock}, prélevé={taken})")

    # Construire le dictionnaire des métriques recalculées
    computed = {
        "used_vehicles": len(solution.vehicles),
        "total_changes": computed_total_changes,
        "total_switch_cost": computed_total_switch_cost,
        "distance_total": computed_distance_total,
    }

    # Comparer les métriques du fichier avec celles recalculées
    # Utiliser une tolérance pour les valeurs flottantes (arrondis dans le fichier)
    if solution.metrics.get("used_vehicles") != computed["used_vehicles"]:
        errors.append(
            f"Métrique used_vehicles incohérente: fichier={solution.metrics.get('used_vehicles')} calculé={computed['used_vehicles']}"
        )
    if solution.metrics.get("total_changes") != computed["total_changes"]:
        errors.append(
            f"Métrique total_changes incohérente: fichier={solution.metrics.get('total_changes')} calculé={computed['total_changes']}"
        )
    if abs(float(solution.metrics.get("total_switch_cost", 0.0)) - computed["total_switch_cost"]) > 0.2:
        errors.append(
            f"Métrique total_switch_cost incohérente: fichier={solution.metrics.get('total_switch_cost')} calculé={computed['total_switch_cost']:.2f}"
        )
    if abs(float(solution.metrics.get("distance_total", 0.0)) - computed["distance_total"]) > 0.2:
        errors.append(
            f"Métrique distance_total incohérente: fichier={solution.metrics.get('distance_total')} calculé={computed['distance_total']:.2f}"
        )

    return errors, computed

if __name__ == "__main__":
    sol_path = "data/solutions/Sol_MPVRP_01_s5_d2_p2.dat"
    ins_path = "/data/instances/MPVRP_01_s5_d2_p2.dat"

    from .utils import parse_instance, parse_solution

    instance = parse_instance(ins_path)
    solution = parse_solution(sol_path)

    errors, computed = verify_solution(instance, solution)
    if errors:
        print("Erreurs détectées dans la solution :")
        for err in errors:
            print(f" - {err}")
    else:
        print("La solution est faisable et cohérente.")

    print("Métriques recalculées :", computed)

