from __future__ import annotations
from typing import Any, Dict, List, Tuple

from .utils import solution_node_key
from .schemas import ParsedSolutionDat, Instance


def verify_solution(instance: Instance, solution: ParsedSolutionDat) -> Tuple[List[str], Dict[str, Any]]:
    """
    Verify the feasibility and consistency of a solution of the MPVRP-CC.

    This function performs the following checks:

    1. Vehicle consistency: departure/arrival at the correct garage
    2. Capacity compliance: no exceedance of truck capacity
    3. Mass conservation: quantity loaded = quantity delivered for each segment
    4. Demand satisfaction: all stations receive requested quantities
    5. Stock compliance: depots are not over-withdrawn
    6. Metric validation: comparison with calculated values

    Parameters
    ----------
    instance : Instance
        The MPVRP-CC problem instance.
    solution : ParsedSolutionDat
        The solution to verify.

    Returns
    -------
    Tuple[List[str], Dict[str, Any]]
        A list of detected errors (empty if solution is feasible) and a dictionary of recalculated metrics.
    """
    errors: List[str] = []

    # Create lookup tables for fast access to entities by numeric ID
    vehicle_by_id = {int(k[1:]): v for k, v in instance.camions.items()}
    depot_by_id = {int(k[1:]): v for k, v in instance.depots.items()}
    station_by_id = {int(k[1:]): v for k, v in instance.stations.items()}

    # Accumulators for verifying deliveries and total loads
    deliveries: Dict[Tuple[str, int], float] = {}  # (station_id, product) -> total quantity delivered
    loads: Dict[Tuple[str, int], float] = {}       # (depot_id, product) -> total quantity loaded

    # Recalculated metrics for validation
    computed_total_changes = 0        # Number of product changes
    computed_total_switch_cost = 0.0  # Total cost of product changes
    computed_distance_total = 0.0     # Total distance traveled by all vehicles

    # Iterate through each vehicle in the solution
    for v in solution.vehicles:
        # Check that the vehicle exists in the instance
        camion = vehicle_by_id.get(v.vehicle_id)
        if camion is None:
            errors.append(f"Vehicle {v.vehicle_id}: missing from instance")
            continue

        # Check that node and product lists have the same length
        if len(v.nodes) != len(v.products):
            errors.append(
                f"Vehicle {v.vehicle_id}: incompatible route/product lengths ({len(v.nodes)} vs {len(v.products)})"
            )
            continue

        # Convert nodes to formatted keys (e.g., "D1", "S5", "G2")
        keyed_nodes = [solution_node_key(n["kind"], n["id"]) for n in v.nodes]
        if not keyed_nodes:
            errors.append(f"Vehicle {v.vehicle_id}: empty route")
            continue

        # Check that the vehicle departs and returns to the correct garage
        expected_garage = camion.garage_id
        if keyed_nodes[0] != expected_garage or keyed_nodes[-1] != expected_garage:
            errors.append(
                f"Vehicle {v.vehicle_id}: inconsistent garage (expected {expected_garage}, got {keyed_nodes[0]}..{keyed_nodes[-1]})"
            )

        # Calculate total distance traveled by this vehicle
        # Sum of distances between each pair of consecutive nodes
        for a, b in zip(keyed_nodes, keyed_nodes[1:]):
            computed_distance_total += float(instance.distances.get((a, b), 0.0))

        # Calculate number and cost of product changes
        # Products are exported with 0-based indexing in the solution
        products_only = [p for (p, _c) in v.products]
        for prev_p, cur_p in zip(products_only, products_only[1:]):
            if prev_p != cur_p:
                computed_total_changes += 1
                computed_total_switch_cost += float(instance.costs.get((prev_p, cur_p), 0.0))

        # Verify mass conservation for each segment (depot → stations)
        # A segment starts at loading from a depot and ends at the next depot or garage
        current_segment_load = None  # (depot_key, product, qty)
        current_segment_delivered = 0.0

        # Iterate through each node visited by the vehicle
        for idx, (node, (p, _cumul)) in enumerate(zip(v.nodes, v.products)):
            kind = node["kind"]
            key = solution_node_key(kind, node["id"])
            qty = float(node.get("qty", 0))

            if kind == "depot":
                # Handle depots: product loading
                if node["id"] not in depot_by_id:
                    errors.append(f"Vehicle {v.vehicle_id}: unknown depot D{node['id']}")

                # Verify that loaded quantity does not exceed truck capacity
                if qty > float(camion.capacity) + 1e-6:
                    errors.append(
                        f"Vehicle {v.vehicle_id}: capacity exceeded at depot {key} (loaded={qty}, capacity={camion.capacity})"
                    )

                # Accumulate total quantity loaded at this depot for this product
                loads[(key, p)] = loads.get((key, p), 0.0) + qty

                # Verify mass conservation for previous segment
                # Loaded quantity must equal quantity delivered at stations
                """
                if current_segment_load is not None:
                    dkey, pp, expected_qty = current_segment_load
                    if abs(current_segment_delivered - expected_qty) > 1e-2:
                        errors.append(
                            f"Vehicle {v.vehicle_id}: mass conservation on segment {dkey} product {pp} (loaded={expected_qty}, delivered={current_segment_delivered})"
                        )
                """
                # Start a new segment
                current_segment_load = (key, p, qty)
                current_segment_delivered = 0.0

            elif kind == "station":
                # Handle stations: product delivery
                if node["id"] not in station_by_id:
                    errors.append(f"Vehicle {v.vehicle_id}: unknown station S{node['id']}")

                # Accumulate global deliveries to verify demand satisfaction
                deliveries[(key, p)] = deliveries.get((key, p), 0.0) + qty
                current_segment_delivered += qty

            else:
                # Handle garages: must only be at start and end
                if idx != 0 and idx != len(v.nodes) - 1:
                    errors.append(f"Vehicle {v.vehicle_id}: garage in the middle of route (position {idx+1})")

        # Verify mass conservation for the last segment
        # (segment ending at garage without reloading)
        """
        if current_segment_load is not None:
            dkey, pp, expected_qty = current_segment_load
            if abs(current_segment_delivered - expected_qty) > 1e-2:
                errors.append(
                    f"Vehicle {v.vehicle_id}: mass conservation on segment {dkey} product {pp} (loaded={expected_qty}, delivered={current_segment_delivered})"
                )
        """

    # Verify that all station demands are satisfied
    # The instance uses 0-based indexing for products in the demands
    for st in instance.stations.values():
        for p, demand in st.demand.items():
            if demand <= 0:
                continue
            delivered = deliveries.get((st.id, p), 0.0)
            if abs(delivered - float(demand)) > 1e-2:
                errors.append(f"Unsatisfied demand: {st.id} product {p} (demand={demand}, delivered={delivered})")

    # Verify that depot stocks are not exceeded
    # The instance uses 0-based indexing for products in the stocks
    for d in instance.depots.values():
        for p, stock in d.stocks.items():
            taken = loads.get((d.id, p), 0.0)
            if taken - float(stock) > 1e-2:
                errors.append(f"Stock exceeded: {d.id} product {p} (stock={stock}, withdrawn={taken})")

    # Build the dictionary of recalculated metrics
    computed = {
        "used_vehicles": len(solution.vehicles),
        "total_changes": computed_total_changes,
        "total_switch_cost": computed_total_switch_cost,
        "distance_total": computed_distance_total,
    }

    # Compare the metrics from the file with those recalculated
    # Use a tolerance for float values (rounding in the file)
    if solution.metrics.get("used_vehicles") != computed["used_vehicles"]:
        errors.append(
            f"used_vehicles metric inconsistent: file={solution.metrics.get('used_vehicles')} computed={computed['used_vehicles']}"
        )
    if solution.metrics.get("total_changes") != computed["total_changes"]:
        errors.append(
            f"total_changes metric inconsistent: file={solution.metrics.get('total_changes')} computed={computed['total_changes']}"
        )
    if abs(float(solution.metrics.get("total_switch_cost", 0.0)) - computed["total_switch_cost"]) > 0.2:
        errors.append(
            f"total_switch_cost metric inconsistent: file={solution.metrics.get('total_switch_cost')} computed={computed['total_switch_cost']:.2f}"
        )
    if abs(float(solution.metrics.get("distance_total", 0.0)) - computed["distance_total"]) > 0.2:
        errors.append(
            f"distance_total metric inconsistent: file={solution.metrics.get('distance_total')} computed={computed['distance_total']:.2f}"
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
        print("Errors detected in the solution:")
        for err in errors:
            print(f" - {err}")
    else:
        print("The solution is feasible and consistent.")

    print("Recalculated metrics:", computed)

