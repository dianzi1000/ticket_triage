import os
import sqlite3
import tempfile

import pytest

from app.database import init_db, save_triage_result
from app.schemas import (
    RecommendedTeam,
    Sentiment,
    TicketCategory,
    TicketInput,
    TicketPriority,
    TicketTriageResult,
)


def make_result(**overrides) -> TicketTriageResult:
    defaults = dict(
        category=TicketCategory.technical_issue,
        priority=TicketPriority.medium,
        sentiment=Sentiment.neutral,
        recommended_team=RecommendedTeam.support,
        short_summary="Test summary",
        suggested_reply="Test reply",
        confidence=0.9,
        needs_escalation=False,
    )
    defaults.update(overrides)
    return TicketTriageResult(**defaults)


def make_ticket(**overrides) -> TicketInput:
    defaults = dict(
        title="Login not working",
        description="User cannot log in to the dashboard.",
        customer_tier="standard",
        product_name="App",
    )
    defaults.update(overrides)
    return TicketInput(**defaults)


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """Point every test at a fresh temporary SQLite file."""
    db_file = str(tmp_path / "test_triage.db")
    monkeypatch.setenv("TRIAGE_DB_PATH", db_file)
    init_db()
    return db_file


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_creates_table(self, isolated_db):
        conn = sqlite3.connect(isolated_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='triage_results'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_idempotent_second_call(self, isolated_db):
        """Calling init_db a second time should not raise."""
        init_db()

    def test_table_has_expected_columns(self, isolated_db):
        conn = sqlite3.connect(isolated_db)
        cursor = conn.execute("PRAGMA table_info(triage_results)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "id", "title", "description", "customer_tier",
            "product_name", "model_result", "final_result", "created_at",
        }
        assert expected.issubset(columns)
        conn.close()


# ---------------------------------------------------------------------------
# save_triage_result
# ---------------------------------------------------------------------------

class TestSaveTriageResult:
    def test_saves_one_record(self, isolated_db):
        ticket = make_ticket()
        model_result = make_result(confidence=0.8)
        final_result = make_result(confidence=0.8, needs_escalation=True)

        save_triage_result(ticket, model_result, final_result)

        conn = sqlite3.connect(isolated_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM triage_results").fetchone()
        assert row is not None
        assert row["title"] == ticket.title
        assert row["description"] == ticket.description
        assert row["customer_tier"] == ticket.customer_tier
        assert row["product_name"] == ticket.product_name
        conn.close()

    def test_model_result_json_stored(self, isolated_db):
        import json

        ticket = make_ticket()
        model_result = make_result(confidence=0.72, category=TicketCategory.billing)
        final_result = make_result(confidence=0.72)

        save_triage_result(ticket, model_result, final_result)

        conn = sqlite3.connect(isolated_db)
        row = conn.execute("SELECT model_result FROM triage_results").fetchone()
        data = json.loads(row[0])
        assert data["category"] == "billing"
        assert data["confidence"] == 0.72
        conn.close()

    def test_final_result_json_stored(self, isolated_db):
        import json

        ticket = make_ticket()
        model_result = make_result()
        final_result = make_result(needs_escalation=True, priority=TicketPriority.urgent)

        save_triage_result(ticket, model_result, final_result)

        conn = sqlite3.connect(isolated_db)
        row = conn.execute("SELECT final_result FROM triage_results").fetchone()
        data = json.loads(row[0])
        assert data["needs_escalation"] is True
        assert data["priority"] == "urgent"
        conn.close()

    def test_created_at_is_stored(self, isolated_db):
        ticket = make_ticket()
        save_triage_result(ticket, make_result(), make_result())

        conn = sqlite3.connect(isolated_db)
        row = conn.execute("SELECT created_at FROM triage_results").fetchone()
        assert row[0] is not None and len(row[0]) > 0
        conn.close()

    def test_null_optional_fields_stored(self, isolated_db):
        ticket = make_ticket(customer_tier=None, product_name=None)
        save_triage_result(ticket, make_result(), make_result())

        conn = sqlite3.connect(isolated_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT customer_tier, product_name FROM triage_results").fetchone()
        assert row["customer_tier"] is None
        assert row["product_name"] is None
        conn.close()

    def test_multiple_records_saved(self, isolated_db):
        for i in range(3):
            ticket = make_ticket(title=f"Ticket {i} title", description=f"Description for ticket number {i}")
            save_triage_result(ticket, make_result(), make_result())

        conn = sqlite3.connect(isolated_db)
        count = conn.execute("SELECT COUNT(*) FROM triage_results").fetchone()[0]
        assert count == 3
        conn.close()
