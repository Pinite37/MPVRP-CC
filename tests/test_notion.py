from datetime import datetime, timezone

import pytest

from backup.database import notion


class _FakePages:
    def __init__(self):
        self.updated = []
        self.created = []

    def update(self, **kwargs):
        self.updated.append(kwargs)
        return {"id": kwargs.get("page_id", "updated")}

    def create(self, **kwargs):
        self.created.append(kwargs)
        return {"id": "new-page"}


class _FakeNotion:
    def __init__(self):
        self.pages = _FakePages()


def test_compute_rankings_orders_by_score_then_submission_date():
    entries = [
        {
            "id": "late",
            "properties": {
                "Score": {"type": "number", "number": 10},
                "Submission Date": {"type": "date", "date": {"start": "2026-03-30T11:00:00+00:00"}},
            },
        },
        {
            "id": "early",
            "properties": {
                "Score": {"type": "number", "number": 10},
                "Submission Date": {"type": "date", "date": {"start": "2026-03-30T10:00:00+00:00"}},
            },
        },
        {
            "id": "no-score",
            "properties": {
                "Score": {"type": "number", "number": None},
                "Submission Date": {"type": "date", "date": {"start": "2026-03-30T09:00:00+00:00"}},
            },
        },
    ]

    rankings = notion._compute_rankings(entries)

    assert rankings["early"] == 1
    assert rankings["late"] == 2
    assert rankings["no-score"] == 3


def test_upsert_submission_updates_existing_email(monkeypatch):
    fake_notion = _FakeNotion()
    monkeypatch.setattr(notion, "notion", fake_notion)

    existing_entry = {
        "id": "page-1",
        "properties": {
            "Email": {"type": "email", "email": "team@example.com"},
            "Rank": {"type": "number", "number": 2},
        },
        "parent": {"database_id": "db-1"},
    }

    def fake_entries(_data_source_id):
        return [existing_entry]

    monkeypatch.setattr(notion, "get_all_entries", fake_entries)

    page_id = notion.upsert_submission(
        data_source_id="source-1",
        email="team@example.com",
        score=100.0,
        feasible_solutions=150,
        name="Team",
    )

    assert page_id == "page-1"
    assert fake_notion.pages.created == []
    assert any(call["page_id"] == "page-1" for call in fake_notion.pages.updated)


def test_upsert_submission_requires_name_for_new_entry(monkeypatch):
    fake_notion = _FakeNotion()
    monkeypatch.setattr(notion, "notion", fake_notion)
    monkeypatch.setattr(notion, "get_all_entries", lambda _id: [])

    with pytest.raises(ValueError):
        notion.upsert_submission(
            data_source_id="source-1",
            email="new@example.com",
            score=100.0,
            feasible_solutions=100,
            name=None,
        )


def test_extract_value_handles_date_and_created_time():
    date_prop = {"type": "date", "date": {"start": "2026-03-30T09:29:24+00:00"}}
    created_prop = {"type": "created_time", "created_time": datetime.now(timezone.utc).isoformat()}

    assert notion._extract_value(date_prop) == "2026-03-30T09:29:24+00:00"
    assert notion._extract_value(created_prop) is not None

