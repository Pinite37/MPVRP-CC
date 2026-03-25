import pytest

from backup.core.model.feasibility import verify_solution
from backup.core.model.schemas import (
    Camion, Depot, Garage, Station, Instance,
    ParsedSolutionVehicle, ParsedSolutionDat
)
from backup.core.model.utils import euclidean_distance


class TestVerifySolutionBasic:
    """Basic test suite for verify_solution function."""

    @pytest.fixture
    def minimal_instance(self):
        """Create a minimal valid instance for testing."""
        camion = Camion(id="K1", capacity=5000.0, garage_id=1, initial_product=0)
        depot = Depot(id="D1", location=(50.0, 50.0), stocks={0: 3000, 1: 2000})
        garage = Garage(id="G1", location=(0.0, 0.0))
        station = Station(id="S1", location=(25.0, 25.0), demand={0: 1000, 1: 500})
        
        # Compute distances
        locations = {"G1": (0.0, 0.0), "D1": (50.0, 50.0), "S1": (25.0, 25.0)}
        distances = {}
        for id1, loc1 in locations.items():
            for id2, loc2 in locations.items():
                distances[(id1, id2)] = euclidean_distance(loc1, loc2)
        
        return Instance(
            num_products=2,
            num_camions=1,
            num_depots=1,
            num_garages=1,
            num_stations=1,
            camions={"K1": camion},
            depots={"D1": depot},
            garages={"G1": garage},
            stations={"S1": station},
            costs={(0, 0): 0.0, (0, 1): 10.0, (1, 0): 10.0, (1, 1): 0.0},
            distances=distances
        )

    @pytest.fixture
    def valid_solution(self):
        """Create a valid solution for the minimal instance."""
        vehicle = ParsedSolutionVehicle(
            vehicle_id=1,
            nodes=[
                {"kind": "garage", "id": 1, "qty": 0},
                {"kind": "depot", "id": 1, "qty": 1000},
                {"kind": "station", "id": 1, "qty": 1000},
                {"kind": "depot", "id": 1, "qty": 500},
                {"kind": "station", "id": 1, "qty": 500},
                {"kind": "garage", "id": 1, "qty": 0},
            ],
            products=[
                (0, 0.0), (0, 0.0), (0, 0.0),
                (1, 10.0), (1, 10.0), (1, 10.0)
            ]
        )
        
        return ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={
                "used_vehicles": 1,
                "total_changes": 1,
                "total_switch_cost": 10.0,
                "distance_total": 200.0,  # Approximate
                "processor": "test",
                "time": 1.0
            }
        )

    def test_verify_returns_tuple(self, minimal_instance, valid_solution):
        """Test that verify_solution returns a tuple."""
        result = verify_solution(minimal_instance, valid_solution)
        
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_verify_returns_errors_list(self, minimal_instance, valid_solution):
        """Test that first element is errors list."""
        errors, _ = verify_solution(minimal_instance, valid_solution)
        
        assert isinstance(errors, list)

    def test_verify_returns_metrics_dict(self, minimal_instance, valid_solution):
        """Test that second element is metrics dictionary."""
        _, metrics = verify_solution(minimal_instance, valid_solution)
        
        assert isinstance(metrics, dict)
        assert "used_vehicles" in metrics
        assert "total_changes" in metrics
        assert "total_switch_cost" in metrics
        assert "distance_total" in metrics


class TestVerifySolutionVehicleConsistency:
    """Test suite for vehicle consistency verification."""

    @pytest.fixture
    def instance_two_garages(self):
        """Create an instance with two garages."""
        camion1 = Camion(id="K1", capacity=5000.0, garage_id=1, initial_product=0)
        camion2 = Camion(id="K2", capacity=5000.0, garage_id=2, initial_product=0)
        depot = Depot(id="D1", location=(50.0, 50.0), stocks={0: 5000})
        garage1 = Garage(id="G1", location=(0.0, 0.0))
        garage2 = Garage(id="G2", location=(100.0, 100.0))
        station = Station(id="S1", location=(25.0, 25.0), demand={0: 2000})
        
        locations = {"G1": (0.0, 0.0), "G2": (100.0, 100.0), 
                    "D1": (50.0, 50.0), "S1": (25.0, 25.0)}
        distances = {}
        for id1, loc1 in locations.items():
            for id2, loc2 in locations.items():
                distances[(id1, id2)] = euclidean_distance(loc1, loc2)
        
        return Instance(
            num_products=1,
            num_camions=2,
            num_depots=1,
            num_garages=2,
            num_stations=1,
            camions={"K1": camion1, "K2": camion2},
            depots={"D1": depot},
            garages={"G1": garage1, "G2": garage2},
            stations={"S1": station},
            costs={(0, 0): 0.0},
            distances=distances
        )

    def test_vehicle_wrong_garage(self, instance_two_garages):
        """Test detection of vehicle starting/ending at wrong garage."""
        # Vehicle 1 should use G1, but solution has it using G2
        vehicle = ParsedSolutionVehicle(
            vehicle_id=1,
            nodes=[
                {"kind": "garage", "id": 2, "qty": 0},  # Wrong garage!
                {"kind": "depot", "id": 1, "qty": 2000},
                {"kind": "station", "id": 1, "qty": 2000},
                {"kind": "garage", "id": 2, "qty": 0},  # Wrong garage!
            ],
            products=[(0, 0.0), (0, 0.0), (0, 0.0), (0, 0.0)]
        )
        
        solution = ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={"used_vehicles": 1, "total_changes": 0, 
                    "total_switch_cost": 0.0, "distance_total": 100.0,
                    "processor": "test", "time": 1.0}
        )
        
        errors, _ = verify_solution(instance_two_garages, solution)
        
        assert any("garage" in e.lower() for e in errors)

    def test_vehicle_not_in_instance(self, instance_two_garages):
        """Test detection of vehicle not in instance."""
        vehicle = ParsedSolutionVehicle(
            vehicle_id=99,  # Non-existent vehicle
            nodes=[
                {"kind": "garage", "id": 1, "qty": 0},
                {"kind": "garage", "id": 1, "qty": 0},
            ],
            products=[(0, 0.0), (0, 0.0)]
        )
        
        solution = ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={"used_vehicles": 1, "total_changes": 0,
                    "total_switch_cost": 0.0, "distance_total": 0.0,
                    "processor": "test", "time": 1.0}
        )
        
        errors, _ = verify_solution(instance_two_garages, solution)
        
        assert any("absent" in e.lower() or "99" in e for e in errors)

    def test_empty_route(self, instance_two_garages):
        """Test detection of empty vehicle route."""
        vehicle = ParsedSolutionVehicle(
            vehicle_id=1,
            nodes=[],  # Empty route
            products=[]
        )
        
        solution = ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={"used_vehicles": 1, "total_changes": 0,
                    "total_switch_cost": 0.0, "distance_total": 0.0,
                    "processor": "test", "time": 1.0}
        )
        
        errors, _ = verify_solution(instance_two_garages, solution)
        
        assert any("vide" in e.lower() or "empty" in e.lower() for e in errors)


class TestVerifySolutionCapacity:
    """Test suite for capacity verification."""

    @pytest.fixture
    def capacity_instance(self):
        """Create an instance for capacity testing."""
        camion = Camion(id="K1", capacity=1000.0, garage_id=1, initial_product=0)
        depot = Depot(id="D1", location=(50.0, 50.0), stocks={0: 5000})
        garage = Garage(id="G1", location=(0.0, 0.0))
        station = Station(id="S1", location=(25.0, 25.0), demand={0: 500})
        
        locations = {"G1": (0.0, 0.0), "D1": (50.0, 50.0), "S1": (25.0, 25.0)}
        distances = {}
        for id1, loc1 in locations.items():
            for id2, loc2 in locations.items():
                distances[(id1, id2)] = euclidean_distance(loc1, loc2)
        
        return Instance(
            num_products=1,
            num_camions=1,
            num_depots=1,
            num_garages=1,
            num_stations=1,
            camions={"K1": camion},
            depots={"D1": depot},
            garages={"G1": garage},
            stations={"S1": station},
            costs={(0, 0): 0.0},
            distances=distances
        )

    def test_capacity_exceeded(self, capacity_instance):
        """Test detection of capacity exceeded."""
        vehicle = ParsedSolutionVehicle(
            vehicle_id=1,
            nodes=[
                {"kind": "garage", "id": 1, "qty": 0},
                {"kind": "depot", "id": 1, "qty": 5000},  # Way over capacity!
                {"kind": "station", "id": 1, "qty": 5000},
                {"kind": "garage", "id": 1, "qty": 0},
            ],
            products=[(0, 0.0), (0, 0.0), (0, 0.0), (0, 0.0)]
        )
        
        solution = ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={"used_vehicles": 1, "total_changes": 0,
                    "total_switch_cost": 0.0, "distance_total": 100.0,
                    "processor": "test", "time": 1.0}
        )
        
        errors, _ = verify_solution(capacity_instance, solution)
        
        assert any("capacité" in e.lower() or "capacity" in e.lower() for e in errors)

"""
class TestVerifySolutionMassConservation:
    # Test suite for mass conservation verification.

    @pytest.fixture
    def mass_instance(self):
        # Create an instance for mass conservation testing.
        camion = Camion(id="K1", capacity=5000.0, garage_id=1, initial_product=0)
        depot = Depot(id="D1", location=(50.0, 50.0), stocks={0: 5000})
        garage = Garage(id="G1", location=(0.0, 0.0))
        station1 = Station(id="S1", location=(25.0, 25.0), demand={0: 500})
        station2 = Station(id="S2", location=(75.0, 75.0), demand={0: 500})
        
        locations = {"G1": (0.0, 0.0), "D1": (50.0, 50.0), 
                    "S1": (25.0, 25.0), "S2": (75.0, 75.0)}
        distances = {}
        for id1, loc1 in locations.items():
            for id2, loc2 in locations.items():
                distances[(id1, id2)] = euclidean_distance(loc1, loc2)
        
        return Instance(
            num_products=1,
            num_camions=1,
            num_depots=1,
            num_garages=1,
            num_stations=2,
            camions={"K1": camion},
            depots={"D1": depot},
            garages={"G1": garage},
            stations={"S1": station1, "S2": station2},
            costs={(0, 0): 0.0},
            distances=distances
        )

    def test_mass_conservation_violation(self, mass_instance):
        # Test detection of mass conservation violation.
        vehicle = ParsedSolutionVehicle(
            vehicle_id=1,
            nodes=[
                {"kind": "garage", "id": 1, "qty": 0},
                {"kind": "depot", "id": 1, "qty": 1000},  # Load 1000
                {"kind": "station", "id": 1, "qty": 600},  # Deliver 600
                {"kind": "station", "id": 2, "qty": 600},  # Deliver 600 (total 1200 > 1000!)
                {"kind": "garage", "id": 1, "qty": 0},
            ],
            products=[(0, 0.0), (0, 0.0), (0, 0.0), (0, 0.0), (0, 0.0)]
        )
        
        solution = ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={"used_vehicles": 1, "total_changes": 0,
                    "total_switch_cost": 0.0, "distance_total": 100.0,
                    "processor": "test", "time": 1.0}
        )
        
        errors, _ = verify_solution(mass_instance, solution)
        
        # assert any("conservation" in e.lower() or "masse" in e.lower() for e in errors)
"""

class TestVerifySolutionDemandSatisfaction:
    """Test suite for demand satisfaction verification."""

    @pytest.fixture
    def demand_instance(self):
        """Create an instance for demand testing."""
        camion = Camion(id="K1", capacity=5000.0, garage_id=1, initial_product=0)
        depot = Depot(id="D1", location=(50.0, 50.0), stocks={0: 5000})
        garage = Garage(id="G1", location=(0.0, 0.0))
        station = Station(id="S1", location=(25.0, 25.0), demand={0: 1000})
        
        locations = {"G1": (0.0, 0.0), "D1": (50.0, 50.0), "S1": (25.0, 25.0)}
        distances = {}
        for id1, loc1 in locations.items():
            for id2, loc2 in locations.items():
                distances[(id1, id2)] = euclidean_distance(loc1, loc2)
        
        return Instance(
            num_products=1,
            num_camions=1,
            num_depots=1,
            num_garages=1,
            num_stations=1,
            camions={"K1": camion},
            depots={"D1": depot},
            garages={"G1": garage},
            stations={"S1": station},
            costs={(0, 0): 0.0},
            distances=distances
        )

    def test_demand_not_satisfied(self, demand_instance):
        """Test detection of unsatisfied demand."""
        vehicle = ParsedSolutionVehicle(
            vehicle_id=1,
            nodes=[
                {"kind": "garage", "id": 1, "qty": 0},
                {"kind": "depot", "id": 1, "qty": 500},
                {"kind": "station", "id": 1, "qty": 500},  # Only 500, demand is 1000
                {"kind": "garage", "id": 1, "qty": 0},
            ],
            products=[(0, 0.0), (0, 0.0), (0, 0.0), (0, 0.0)]
        )
        
        solution = ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={"used_vehicles": 1, "total_changes": 0,
                    "total_switch_cost": 0.0, "distance_total": 100.0,
                    "processor": "test", "time": 1.0}
        )
        
        errors, _ = verify_solution(demand_instance, solution)
        
        assert any("demande" in e.lower() or "demand" in e.lower() for e in errors)


class TestVerifySolutionStockLimits:
    """Test suite for stock limit verification."""

    @pytest.fixture
    def stock_instance(self):
        """Create an instance for stock testing."""
        camion = Camion(id="K1", capacity=10000.0, garage_id=1, initial_product=0)
        depot = Depot(id="D1", location=(50.0, 50.0), stocks={0: 500})  # Limited stock
        garage = Garage(id="G1", location=(0.0, 0.0))
        station = Station(id="S1", location=(25.0, 25.0), demand={0: 500})
        
        locations = {"G1": (0.0, 0.0), "D1": (50.0, 50.0), "S1": (25.0, 25.0)}
        distances = {}
        for id1, loc1 in locations.items():
            for id2, loc2 in locations.items():
                distances[(id1, id2)] = euclidean_distance(loc1, loc2)
        
        return Instance(
            num_products=1,
            num_camions=1,
            num_depots=1,
            num_garages=1,
            num_stations=1,
            camions={"K1": camion},
            depots={"D1": depot},
            garages={"G1": garage},
            stations={"S1": station},
            costs={(0, 0): 0.0},
            distances=distances
        )

    def test_stock_exceeded(self, stock_instance):
        """Test detection of stock exceeded."""
        vehicle = ParsedSolutionVehicle(
            vehicle_id=1,
            nodes=[
                {"kind": "garage", "id": 1, "qty": 0},
                {"kind": "depot", "id": 1, "qty": 5000},  # Taking more than stock
                {"kind": "station", "id": 1, "qty": 5000},
                {"kind": "garage", "id": 1, "qty": 0},
            ],
            products=[(0, 0.0), (0, 0.0), (0, 0.0), (0, 0.0)]
        )
        
        solution = ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={"used_vehicles": 1, "total_changes": 0,
                    "total_switch_cost": 0.0, "distance_total": 100.0,
                    "processor": "test", "time": 1.0}
        )
        
        errors, _ = verify_solution(stock_instance, solution)
        
        assert any("stock" in e.lower() for e in errors)


class TestVerifySolutionMetrics:
    """Test suite for metrics validation."""

    @pytest.fixture
    def metrics_instance(self):
        """Create an instance for metrics testing."""
        camion = Camion(id="K1", capacity=5000.0, garage_id=1, initial_product=0)
        depot = Depot(id="D1", location=(50.0, 50.0), stocks={0: 3000, 1: 2000})
        garage = Garage(id="G1", location=(0.0, 0.0))
        station = Station(id="S1", location=(25.0, 25.0), demand={0: 1000, 1: 500})
        
        locations = {"G1": (0.0, 0.0), "D1": (50.0, 50.0), "S1": (25.0, 25.0)}
        distances = {}
        for id1, loc1 in locations.items():
            for id2, loc2 in locations.items():
                distances[(id1, id2)] = euclidean_distance(loc1, loc2)
        
        return Instance(
            num_products=2,
            num_camions=1,
            num_depots=1,
            num_garages=1,
            num_stations=1,
            camions={"K1": camion},
            depots={"D1": depot},
            garages={"G1": garage},
            stations={"S1": station},
            costs={(0, 0): 0.0, (0, 1): 15.0, (1, 0): 15.0, (1, 1): 0.0},
            distances=distances
        )

    def test_wrong_vehicle_count(self, metrics_instance):
        """Test detection of wrong vehicle count in metrics."""
        vehicle = ParsedSolutionVehicle(
            vehicle_id=1,
            nodes=[
                {"kind": "garage", "id": 1, "qty": 0},
                {"kind": "depot", "id": 1, "qty": 1000},
                {"kind": "station", "id": 1, "qty": 1000},
                {"kind": "depot", "id": 1, "qty": 500},
                {"kind": "station", "id": 1, "qty": 500},
                {"kind": "garage", "id": 1, "qty": 0},
            ],
            products=[(0, 0.0), (0, 0.0), (0, 0.0), (1, 15.0), (1, 15.0), (1, 15.0)]
        )
        
        solution = ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={
                "used_vehicles": 5,  # Wrong! Should be 1
                "total_changes": 1,
                "total_switch_cost": 15.0,
                "distance_total": 200.0,
                "processor": "test",
                "time": 1.0
            }
        )
        
        errors, computed = verify_solution(metrics_instance, solution)
        
        assert computed["used_vehicles"] == 1
        assert any("used_vehicles" in e for e in errors)

    def test_computed_metrics_returned(self, metrics_instance):
        """Test that computed metrics are returned."""
        vehicle = ParsedSolutionVehicle(
            vehicle_id=1,
            nodes=[
                {"kind": "garage", "id": 1, "qty": 0},
                {"kind": "depot", "id": 1, "qty": 1000},
                {"kind": "station", "id": 1, "qty": 1000},
                {"kind": "depot", "id": 1, "qty": 500},
                {"kind": "station", "id": 1, "qty": 500},
                {"kind": "garage", "id": 1, "qty": 0},
            ],
            products=[(0, 0.0), (0, 0.0), (0, 0.0), (1, 15.0), (1, 15.0), (1, 15.0)]
        )
        
        solution = ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={
                "used_vehicles": 1,
                "total_changes": 1,
                "total_switch_cost": 15.0,
                "distance_total": 200.0,
                "processor": "test",
                "time": 1.0
            }
        )
        
        _, computed = verify_solution(metrics_instance, solution)
        
        assert "used_vehicles" in computed
        assert "total_changes" in computed
        assert "total_switch_cost" in computed
        assert "distance_total" in computed


class TestVerifySolutionProductChanges:
    """Test suite for product change tracking."""

    @pytest.fixture
    def product_instance(self):
        """Create an instance for product change testing."""
        camion = Camion(id="K1", capacity=5000.0, garage_id=1, initial_product=0)
        depot = Depot(id="D1", location=(50.0, 50.0), stocks={0: 5000, 1: 5000, 2: 5000})
        garage = Garage(id="G1", location=(0.0, 0.0))
        station = Station(id="S1", location=(25.0, 25.0), demand={0: 500, 1: 500, 2: 500})
        
        locations = {"G1": (0.0, 0.0), "D1": (50.0, 50.0), "S1": (25.0, 25.0)}
        distances = {}
        for id1, loc1 in locations.items():
            for id2, loc2 in locations.items():
                distances[(id1, id2)] = euclidean_distance(loc1, loc2)
        
        costs = {}
        for i in range(3):
            for j in range(3):
                costs[(i, j)] = 0.0 if i == j else 20.0
        
        return Instance(
            num_products=3,
            num_camions=1,
            num_depots=1,
            num_garages=1,
            num_stations=1,
            camions={"K1": camion},
            depots={"D1": depot},
            garages={"G1": garage},
            stations={"S1": station},
            costs=costs,
            distances=distances
        )

    def test_count_product_changes(self, product_instance):
        """Test that product changes are counted correctly."""
        # Route with 2 product changes: 0->1 and 1->2
        vehicle = ParsedSolutionVehicle(
            vehicle_id=1,
            nodes=[
                {"kind": "garage", "id": 1, "qty": 0},
                {"kind": "depot", "id": 1, "qty": 500},
                {"kind": "station", "id": 1, "qty": 500},
                {"kind": "depot", "id": 1, "qty": 500},
                {"kind": "station", "id": 1, "qty": 500},
                {"kind": "depot", "id": 1, "qty": 500},
                {"kind": "station", "id": 1, "qty": 500},
                {"kind": "garage", "id": 1, "qty": 0},
            ],
            products=[
                (0, 0.0), (0, 0.0), (0, 0.0),  # Product 0
                (1, 20.0), (1, 20.0),           # Product 1 (change)
                (2, 40.0), (2, 40.0),           # Product 2 (change)
                (2, 40.0)
            ]
        )
        
        solution = ParsedSolutionDat(
            vehicles=[vehicle],
            metrics={
                "used_vehicles": 1,
                "total_changes": 2,
                "total_switch_cost": 40.0,
                "distance_total": 200.0,
                "processor": "test",
                "time": 1.0
            }
        )
        
        _, computed = verify_solution(product_instance, solution)
        
        assert computed["total_changes"] == 2
        assert computed["total_switch_cost"] == 40.0
