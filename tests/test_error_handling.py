import json
from unittest.mock import patch, MagicMock

import pytest
from openai import APITimeoutError, APIError

from app.schemas import (
    TicketCategory,
    TicketInput,
    TicketPriority,
    TicketTriageResult,
    RecommendedTeam,
    Sentiment,
)
from app.triage_service import fallback_result, triage_ticket


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ticket(**overrides) -> TicketInput:
    defaults = dict(
        title="Login not working",
        description="User cannot log in to the dashboard.",
        customer_tier="standard",
        product_name="App",
    )
    defaults.update(overrides)
    return TicketInput(**defaults)


# ---------------------------------------------------------------------------
# fallback_result
# ---------------------------------------------------------------------------

class TestFallbackResult:
    def test_returns_expected_defaults(self):
        result = fallback_result("test reason")
        assert result.category == TicketCategory.other
        assert result.priority == TicketPriority.medium
        assert result.sentiment == Sentiment.neutral
        assert result.recommended_team == RecommendedTeam.support
        assert result.confidence == 0.0
        assert result.needs_escalation is False
        assert "test reason" in result.short_summary

    def test_is_valid_triage_result(self):
        result = fallback_result("any reason")
        assert isinstance(result, TicketTriageResult)


# ---------------------------------------------------------------------------
# triage_ticket — model call failures
# ---------------------------------------------------------------------------

class TestTriageTicketModelErrors:
    @patch("app.triage_service.triage_ticket_raw")
    def test_api_timeout_returns_fallback(self, mock_raw):
        mock_raw.side_effect = APITimeoutError(request=MagicMock())
        ticket = make_ticket()
        result = triage_ticket(ticket)
        assert result.confidence == 0.0
        assert result.category == TicketCategory.other
        assert "timeout" in result.short_summary

    @patch("app.triage_service.triage_ticket_raw")
    def test_api_error_returns_fallback(self, mock_raw):
        mock_raw.side_effect = APIError(
            message="server error", request=MagicMock(), body=None
        )
        ticket = make_ticket()
        result = triage_ticket(ticket)
        assert result.confidence == 0.0
        assert result.category == TicketCategory.other
        assert "model error" in result.short_summary

    @patch("app.triage_service.triage_ticket_raw")
    def test_unexpected_exception_returns_fallback(self, mock_raw):
        mock_raw.side_effect = RuntimeError("boom")
        ticket = make_ticket()
        result = triage_ticket(ticket)
        assert result.confidence == 0.0
        assert result.category == TicketCategory.other
        assert "unexpected error" in result.short_summary


# ---------------------------------------------------------------------------
# triage_ticket — bad JSON / validation failures
# ---------------------------------------------------------------------------

class TestTriageTicketParsingErrors:
    @patch("app.triage_service.triage_ticket_raw")
    def test_invalid_json_returns_fallback(self, mock_raw):
        mock_raw.return_value = "not valid json {{"
        ticket = make_ticket()
        result = triage_ticket(ticket)
        assert result.confidence == 0.0
        assert "invalid model response" in result.short_summary

    @patch("app.triage_service.triage_ticket_raw")
    def test_json_with_wrong_schema_returns_fallback(self, mock_raw):
        mock_raw.return_value = json.dumps({"foo": "bar"})
        ticket = make_ticket()
        result = triage_ticket(ticket)
        assert result.confidence == 0.0
        assert "validation error" in result.short_summary

    @patch("app.triage_service.triage_ticket_raw")
    def test_json_with_invalid_enum_returns_fallback(self, mock_raw):
        mock_raw.return_value = json.dumps(
            {
                "category": "INVALID_ENUM",
                "priority": "medium",
                "sentiment": "neutral",
                "recommended_team": "support",
                "short_summary": "test",
                "suggested_reply": "test",
                "confidence": 0.9,
                "needs_escalation": False,
            }
        )
        ticket = make_ticket()
        result = triage_ticket(ticket)
        assert result.confidence == 0.0
        assert "validation error" in result.short_summary


# ---------------------------------------------------------------------------
# triage_ticket — happy path still applies business rules
# ---------------------------------------------------------------------------

class TestTriageTicketHappyPath:
    @patch("app.triage_service.triage_ticket_raw")
    def test_successful_response_applies_business_rules(self, mock_raw):
        mock_raw.return_value = json.dumps(
            {
                "category": "outage",
                "priority": "high",
                "sentiment": "angry",
                "recommended_team": "sre_ops",
                "short_summary": "Service is down",
                "suggested_reply": "We are investigating.",
                "confidence": 0.95,
                "needs_escalation": False,
            }
        )
        ticket = make_ticket()
        result = triage_ticket(ticket)
        # Outage rule should have forced escalation
        assert result.needs_escalation is True
        assert result.confidence == 0.95


# ---------------------------------------------------------------------------
# triage_ticket — fallback still applies business rules
# ---------------------------------------------------------------------------

class TestFallbackAppliesBusinessRules:
    @patch("app.triage_service.triage_ticket_raw")
    def test_fallback_with_production_down_title_gets_urgent(self, mock_raw):
        mock_raw.side_effect = APITimeoutError(request=MagicMock())
        ticket = make_ticket(title="production down everywhere")
        result = triage_ticket(ticket)
        # Fallback gives medium priority, but Rule 2 should bump to urgent
        assert result.priority == TicketPriority.urgent
        assert result.confidence == 0.0
