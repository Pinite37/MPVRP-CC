import io
import uuid

import pytest

# Mark all tests in this module as API tests
pytestmark = [pytest.mark.api, pytest.mark.integration]

# Check if FastAPI and dependencies are available
try:
    from fastapi.testclient import TestClient
    from backup.app.main import app
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    app = None
    TestClient = None


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI or dependencies not available")
class TestApiImports:
    """Test that API modules can be imported."""

    def test_import_main(self):
        """Test importing main app module."""
        from backup.app.main import app
        assert app is not None

    def test_import_schemas(self):
        """Test importing API schemas."""
        from backup.app.schemas import (
            InstanceGenerationRequest,
            SolutionVerificationResponse
        )
        assert InstanceGenerationRequest is not None
        assert SolutionVerificationResponse is not None

    def test_import_routes(self):
        """Test importing route modules."""
        from backup.app.routes import generator, model
        assert generator.router is not None
        assert model.router is not None


class TestApiSchemas:
    """Test suite for API schema validation."""

    def test_instance_generation_request_valid(self):
        """Test valid InstanceGenerationRequest."""
        from backup.app.schemas import InstanceGenerationRequest

        request = InstanceGenerationRequest(
            id_instance="TEST01",
            nb_vehicules=3,
            nb_depots=2,
            nb_garages=1,
            nb_stations=5,
            nb_produits=2
        )

        assert request.id_instance == "TEST01"
        assert request.nb_vehicules == 3
        assert request.nb_depots == 2
        assert request.nb_garages == 1
        assert request.nb_stations == 5
        assert request.nb_produits == 2

    def test_instance_generation_request_defaults(self):
        """Test InstanceGenerationRequest default values."""
        from backup.app.schemas import InstanceGenerationRequest

        request = InstanceGenerationRequest(
            id_instance="TEST01",
            nb_vehicules=3,
            nb_depots=2,
            nb_garages=1,
            nb_stations=5,
            nb_produits=2
        )

        # Check default values
        assert request.max_coord == 100.0
        assert request.min_capacite == 10000
        assert request.max_capacite == 25000
        assert request.min_transition_cost == 10.0
        assert request.max_transition_cost == 80.0
        assert request.min_demand == 500
        assert request.max_demand == 5000
        assert request.seed is None

    def test_instance_generation_request_with_seed(self):
        """Test InstanceGenerationRequest with seed."""
        from backup.app.schemas import InstanceGenerationRequest

        request = InstanceGenerationRequest(
            id_instance="TEST01",
            nb_vehicules=3,
            nb_depots=2,
            nb_garages=1,
            nb_stations=5,
            nb_produits=2,
            seed=42
        )

        assert request.seed == 42

    def test_instance_generation_request_validation(self):
        """Test InstanceGenerationRequest validation."""
        from backup.app.schemas import InstanceGenerationRequest
        from pydantic import ValidationError

        # Should fail with nb_vehicules < 1
        with pytest.raises(ValidationError):
            InstanceGenerationRequest(
                id_instance="TEST01",
                nb_vehicules=0,  # Invalid!
                nb_depots=2,
                nb_garages=1,
                nb_stations=5,
                nb_produits=2
            )

    def test_solution_verification_response(self):
        """Test SolutionVerificationResponse creation."""
        from backup.app.schemas import SolutionVerificationResponse

        response = SolutionVerificationResponse(
            feasible=True,
            errors=[],
            metrics={"distance_total": 150.0, "total_changes": 2}
        )

        assert response.feasible is True
        assert response.errors == []
        assert response.metrics["distance_total"] == 150.0


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI or dependencies not available")
class TestFastAPIAppConfig:
    """Test suite for FastAPI app configuration."""

    def test_app_title(self):
        """Test that app has correct title."""
        from backup.app.main import app

        assert app.title == "MPVRP-CC API"

    def test_app_version(self):
        """Test that app has version."""
        from backup.app.main import app

        assert app.version == "1.0.0"

    def test_app_has_routes(self):
        """Test that app has routes configured."""
        from backup.app.main import app

        routes = [route.path for route in app.routes]

        # Check for main routes
        assert "/" in routes
        assert "/health" in routes

    def test_cors_middleware(self):
        """Test that CORS middleware is configured."""
        from backup.app.main import app

        # Check that middleware is present
        middleware_classes = [type(m).__name__ for m in app.user_middleware]
        # CORS middleware should be configured
        assert len(app.user_middleware) > 0


class TestApiEndpointsWithTestClient:
    """Test suite for API endpoints using TestClient."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        try:
            from fastapi.testclient import TestClient
            from backup.app.main import app
            return TestClient(app)
        except ImportError:
            pytest.skip("fastapi testclient not available")

    def test_root_endpoint(self, client):
        """Test root endpoint returns welcome message."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "MPVRP-CC" in data["message"]

    def test_root_endpoint_head(self, client):
        """Test root endpoint HEAD method."""
        response = client.head("/")

        assert response.status_code == 200

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_endpoint_head(self, client):
        """Test health endpoint HEAD method."""
        response = client.head("/health")

        assert response.status_code == 200

    def test_docs_endpoint(self, client):
        """Test that docs endpoint is available."""
        response = client.get("/docs")

        assert response.status_code == 200

    def test_openapi_json(self, client):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


class TestGeneratorEndpoint:
    """Test suite for generator endpoint."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        try:
            from fastapi.testclient import TestClient
            from backup.app.main import app
            return TestClient(app)
        except ImportError:
            pytest.skip("fastapi testclient not available")

    def test_generate_instance_success(self, client):
        """Test successful instance generation."""
        response = client.post(
            "/generator/generate",
            json={
                "id_instance": "TEST_API",
                "nb_vehicules": 2,
                "nb_depots": 1,
                "nb_garages": 1,
                "nb_stations": 3,
                "nb_produits": 2,
                "seed": 42
            }
        )

        assert response.status_code == 200
        # Response should be a file download
        assert "attachment" in response.headers.get("content-disposition", "")

    def test_generate_instance_with_custom_params(self, client):
        """Test instance generation with custom parameters."""
        response = client.post(
            "/generator/generate",
            json={
                "id_instance": "CUSTOM01",
                "nb_vehicules": 5,
                "nb_depots": 3,
                "nb_garages": 2,
                "nb_stations": 10,
                "nb_produits": 4,
                "max_coord": 200.0,
                "min_capacite": 5000,
                "max_capacite": 15000,
                "seed": 123
            }
        )

        assert response.status_code == 200

    def test_generate_instance_missing_required_field(self, client):
        """Test that missing required fields return 422."""
        response = client.post(
            "/generator/generate",
            json={
                "id_instance": "TEST",
                # Missing other required fields
            }
        )

        assert response.status_code == 422

    def test_generate_instance_invalid_values(self, client):
        """Test that invalid values return error."""
        response = client.post(
            "/generator/generate",
            json={
                "id_instance": "TEST",
                "nb_vehicules": 0,  # Invalid: must be >= 1
                "nb_depots": 1,
                "nb_garages": 1,
                "nb_stations": 3,
                "nb_produits": 2
            }
        )

        assert response.status_code == 422


class TestModelEndpoint:
    """Test suite for model verification endpoint."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        try:
            from fastapi.testclient import TestClient
            from backup.app.main import app

            return TestClient(app)
        except ImportError:
            pytest.skip("fastapi testclient not available")

    @pytest.fixture
    def sample_instance_content(self):
        """Create sample instance file content."""
        return b"""# test-uuid-1234
2\t1\t1\t2\t1
0.0\t15.0
15.0\t0.0
1\t5000\t1\t1
1\t50.0\t50.0\t3000\t2000
1\t0.0\t0.0
1\t25.0\t25.0\t1000\t500
2\t75.0\t75.0\t500\t1000
"""

    @pytest.fixture
    def sample_solution_content(self):
        """Create sample solution file content."""
        return b"""1: 1 - 1 [1500] - 1 (1000) - 2 (500) - 1
1: 0(0.0) - 0(0.0) - 0(0.0) - 0(0.0) - 0(0.0)

1
0
0.00
150.00
test
1.000
"""

    def test_verify_endpoint_exists(self, client):
        """Test that verify endpoint exists."""
        # Just check the endpoint is reachable (even if it fails due to missing files)
        response = client.post("/model/verify")

        # Should return 422 (missing files) not 404
        assert response.status_code == 422

    def test_verify_with_files(self, client, sample_instance_content, sample_solution_content):
        """Test verification with uploaded files."""
        response = client.post(
            "/model/verify",
            files={
                "instance_file": ("instance.dat", io.BytesIO(sample_instance_content), "application/octet-stream"),
                "solution_file": ("solution.dat", io.BytesIO(sample_solution_content), "application/octet-stream"),
            }
        )

        # Should process the files (may have errors in solution, but should return 200 or 400)
        assert response.status_code in [200, 400]

    def test_verify_missing_instance_file(self, client, sample_solution_content):
        """Test verification without instance file."""
        response = client.post(
            "/model/verify",
            files={
                "solution_file": ("solution.dat", io.BytesIO(sample_solution_content), "application/octet-stream"),
            }
        )

        assert response.status_code == 422

    def test_verify_missing_solution_file(self, client, sample_instance_content):
        """Test verification without solution file."""
        response = client.post(
            "/model/verify",
            files={
                "instance_file": ("instance.dat", io.BytesIO(sample_instance_content), "application/octet-stream"),
            }
        )

        assert response.status_code == 422


class TestApiErrorHandling:
    """Test suite for API error handling."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        try:
            from fastapi.testclient import TestClient
            from backup.app.main import app
            return TestClient(app)
        except ImportError:
            pytest.skip("fastapi testclient not available")

    def test_404_for_unknown_endpoint(self, client):
        """Test that unknown endpoints return 404."""
        response = client.get("/unknown/endpoint")

        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test that wrong HTTP methods return appropriate error."""
        # POST to root endpoint should work (it accepts GET/HEAD)
        response = client.post("/")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405

    def test_invalid_json_body(self, client):
        """Test handling of invalid JSON body."""
        response = client.post(
            "/generator/generate",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422


class TestAuthRegisterEndpoint:
    """Test suite for auth registration endpoint."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        try:
            from fastapi.testclient import TestClient
            from backup.app.main import app
            return TestClient(app)
        except ImportError:
            pytest.skip("fastapi testclient not available")

    def test_register_success_with_json_body(self, client):
        """Register should accept JSON body and create a team."""
        suffix = uuid.uuid4().hex[:8]
        payload = {
            "team_name": f"team_{suffix}",
            "email": f"team_{suffix}@example.com",
            "password": "secure-pass-123",
        }

        response = client.post("/auth/register", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["team_name"] == payload["team_name"]
        assert data["email"] == payload["email"]
        assert "id" in data

    def test_register_missing_required_field_returns_422(self, client):
        """Register should return 422 when body is missing required fields."""
        response = client.post(
            "/auth/register",
            json={
                "team_name": "missing_password",
                "email": "missing_password@example.com",
                # missing password
            },
        )

        assert response.status_code == 422

    def test_register_duplicate_team_or_email_returns_400(self, client):
        """Register should reject duplicate team name/email."""
        suffix = uuid.uuid4().hex[:8]
        payload = {
            "team_name": f"dup_team_{suffix}",
            "email": f"dup_team_{suffix}@example.com",
            "password": "secure-pass-123",
        }

        first = client.post("/auth/register", json=payload)
        second = client.post("/auth/register", json=payload)

        assert first.status_code == 200
        assert second.status_code == 400
        assert second.json()["detail"] == "Team name or team email already exists"

