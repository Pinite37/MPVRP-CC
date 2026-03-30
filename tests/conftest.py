"""
Pytest configuration and fixtures for MPVRP-CC test suite.
"""
import os
import sys
import tempfile
import pytest

# Add the project root to sys.path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backup.core.model.schemas import (
    Camion, Depot, Garage, Station, Instance,
    ParsedSolutionVehicle, ParsedSolutionDat
)


# ============================================================================
# API TEST CLIENT
# ============================================================================

@pytest.fixture
def client():
    """Provide a TestClient for API tests."""
    try:
        from fastapi.testclient import TestClient
        from backup.app.main import app
        with TestClient(app) as test_client:
            yield test_client
    except ImportError:
        pytest.skip("fastapi testclient not available")


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_camion():
    """Create a sample Camion (vehicle) instance."""
    return Camion(
        id="K1",
        capacity=10000.0,
        garage_id="G1",
        initial_product=1
    )


@pytest.fixture
def sample_depot():
    """Create a sample Depot instance."""
    return Depot(
        id="D1",
        location=(50.0, 50.0),
        stocks={0: 5000, 1: 3000}
    )


@pytest.fixture
def sample_garage():
    """Create a sample Garage instance."""
    return Garage(
        id="G1",
        location=(0.0, 0.0)
    )


@pytest.fixture
def sample_station():
    """Create a sample Station instance."""
    return Station(
        id="S1",
        location=(25.0, 25.0),
        demand={0: 1000, 1: 500}
    )


@pytest.fixture
def sample_instance(sample_camion, sample_depot, sample_garage, sample_station):
    """Create a minimal valid MPVRP-CC instance."""
    return Instance(
        num_products=2,
        num_camions=1,
        num_depots=1,
        num_garages=1,
        num_stations=1,
        camions={"K1": sample_camion},
        depots={"D1": sample_depot},
        garages={"G1": sample_garage},
        stations={"S1": sample_station},
        costs={(0, 0): 0.0, (0, 1): 10.0, (1, 0): 10.0, (1, 1): 0.0},
        distances={}
    )


@pytest.fixture
def sample_solution_vehicle():
    """Create a sample parsed solution vehicle."""
    return ParsedSolutionVehicle(
        vehicle_id=1,
        nodes=[
            {"kind": "garage", "id": 1, "qty": 0},
            {"kind": "depot", "id": 1, "qty": 1000},
            {"kind": "station", "id": 1, "qty": 1000},
            {"kind": "garage", "id": 1, "qty": 0},
        ],
        products=[(0, 0.0), (0, 0.0), (0, 0.0), (0, 0.0)]
    )


@pytest.fixture
def sample_solution(sample_solution_vehicle):
    """Create a sample parsed solution."""
    return ParsedSolutionDat(
        vehicles=[sample_solution_vehicle],
        metrics={
            "used_vehicles": 1,
            "total_changes": 0,
            "total_switch_cost": 0.0,
            "distance_total": 100.0,
            "processor": "test",
            "time": 1.0
        }
    )


# ============================================================================
# TEMPORARY FILE FIXTURES
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_instance_file(temp_dir):
    """Create a temporary instance file for testing."""
    filepath = os.path.join(temp_dir, "test_instance.dat")
    content = """# test-uuid-1234-5678-9abc-def012345678
2	1	1	2	1
0.0	15.0
15.0	0.0
1	5000	1	1
1	50.0	50.0	3000	2000
1	0.0	0.0
1	25.0	25.0	1000	500
2	75.0	75.0	500	1000
"""
    with open(filepath, 'w') as f:
        f.write(content)
    return filepath


@pytest.fixture
def sample_solution_file(temp_dir):
    """Create a temporary solution file for testing."""
    filepath = os.path.join(temp_dir, "test_solution.dat")
    content = """1: 1 - 1 [1500] - 1 (1000) - 2 (500) - 1
1: 0(0.0) - 0(0.0) - 0(0.0) - 0(0.0) - 0(0.0)

1
0
0.00
150.00
test_processor
1.000
"""
    with open(filepath, 'w') as f:
        f.write(content)
    return filepath


@pytest.fixture
def invalid_instance_file(temp_dir):
    """Create an invalid instance file for testing error handling."""
    filepath = os.path.join(temp_dir, "invalid_instance.dat")
    content = """# invalid-uuid
invalid content here
"""
    with open(filepath, 'w') as f:
        f.write(content)
    return filepath


# ============================================================================
# PARAMETERIZED TEST DATA
# ============================================================================

@pytest.fixture(params=["small", "medium", "large"])
def category_name(request):
    """Parameterized fixture for instance categories."""
    return request.param


@pytest.fixture
def instance_generation_params():
    """Standard parameters for instance generation tests."""
    return {
        "id_inst": "TEST01",
        "nb_v": 2,
        "nb_d": 1,
        "nb_g": 1,
        "nb_s": 3,
        "nb_p": 2,
        "max_coord": 100.0,
        "min_capacite": 5000,
        "max_capacite": 10000,
        "min_transition_cost": 10.0,
        "max_transition_cost": 50.0,
        "min_demand": 100,
        "max_demand": 1000,
        "seed": 42,
        "force_overwrite": True,
        "silent": True
    }


# ============================================================================
# UTILITY FUNCTIONS FOR TESTS
# ============================================================================

@pytest.fixture
def assert_valid_coordinates():
    """Fixture providing coordinate validation function."""
    def _assert(x, y, max_coord):
        assert 0 <= x <= max_coord, f"X coordinate {x} out of bounds [0, {max_coord}]"
        assert 0 <= y <= max_coord, f"Y coordinate {y} out of bounds [0, {max_coord}]"
    return _assert


@pytest.fixture
def assert_positive():
    """Fixture providing positive number validation function."""
    def _assert(value, name="value"):
        assert value > 0, f"{name} must be positive, got {value}"
    return _assert


# ============================================================================
# MARKERS CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "api: marks tests as API tests")
