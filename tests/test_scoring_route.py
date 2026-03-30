import io
import json

import pytest
from fastapi.testclient import TestClient

from backup.app.main import app


@pytest.fixture
def scoring_client():
    with TestClient(app) as test_client:
        yield test_client


def test_scoring_submit_rejects_non_zip(scoring_client):
    response = scoring_client.post(
        "/scoring/submit",
        files={"file": ("solutions.txt", io.BytesIO(b"x"), "text/plain")},
        data={"email": "team@example.com", "name": "Team"},
    )

    assert response.status_code == 400
    assert "zip" in response.json()["detail"].lower()


def test_scoring_submit_returns_formatted_payload(scoring_client, monkeypatch):
    import backup.app.routes.scoring as scoring_route

    monkeypatch.setattr(scoring_route, "DATA_SOURCE_ID", None)
    monkeypatch.setattr(
        scoring_route,
        "process_full_submission",
        lambda _path: {
            "total_weighted_score": 12.345,
            "is_fully_feasible": False,
            "total_feasible_count": 149,
            "category_stats": {"small": 50, "medium": 49, "large": 50},
            "processor_info": "ok",
            "instance_results": [
                {
                    "instance": "Sol_S_001.dat",
                    "category": "small",
                    "feasible": True,
                    "distance": 10.0,
                    "transition_cost": 1.0,
                    "errors": [],
                }
            ],
        },
    )

    response = scoring_client.post(
        "/scoring/submit",
        files={"file": ("solutions.zip", io.BytesIO(b"zip-bytes"), "application/zip")},
        data={"email": "team@example.com", "name": "Team"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_score"] == 12.35
    assert payload["is_fully_feasible"] is False
    assert payload["total_valid_instances"] == "149/150"
    assert json.loads(payload["total_valid_instances_per_category"]) == {
        "small": 50,
        "medium": 49,
        "large": 50,
    }
    assert payload["processor_info"] == "ok"
    assert payload["is_ready"] is True
    assert isinstance(payload["submission_id"], int)
    assert "T" in payload["submitted_at"]

