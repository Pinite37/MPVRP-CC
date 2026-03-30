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


class TestScoreboardEndpoint:
    """Regression tests for scoreboard route payload normalization."""

    def test_extract_value_date_returns_iso_string(self):
        """Notion date property should be normalized to date.start string."""
        from backup.database.notion import _extract_value

        value = _extract_value({
            "type": "date",
            "date": {
                "start": "2026-03-30T09:29:24.160+00:00",
                "end": None,
                "time_zone": None,
            },
        })

        assert value == "2026-03-30T09:29:24.160+00:00"

    def test_scoreboard_handles_notion_date_object(self, client, monkeypatch):
        """/scoreboard should return 200 even when Notion date is nested object."""
        import backup.app.routes.scoreboard as scoreboard_route

        monkeypatch.setattr(scoreboard_route, "DATA_SOURCE_ID", "test-data-source")

        def fake_get_all_entries(_data_source_id):
            return [{
                "properties": {
                    "Rank": {"type": "number", "number": 1},
                    "Name": {"type": "rich_text", "rich_text": [{"plain_text": "Team A"}]},
                    "Score": {"type": "number", "number": 123.456},
                    "Feasible solutions": {"type": "number", "number": 150},
                    "Submission date": {
                        "type": "date",
                        "date": {
                            "start": "2026-03-30T09:29:24.160+00:00",
                            "end": None,
                            "time_zone": None,
                        },
                    },
                }
            }]

        monkeypatch.setattr(scoreboard_route, "get_all_entries", fake_get_all_entries)

        response = client.get("/scoreboard")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["rank"] == 1
        assert data[0]["team"] == "Team A"
        assert data[0]["score"] == 123.46
        assert data[0]["instances_validated"] == "150/150"
        assert data[0]["last_submission"] == "2026-03-30T09:29:24.160+00:00"

