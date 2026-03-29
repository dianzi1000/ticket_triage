import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError

from app.main import app


client = TestClient(app)


class TestTriageEndpointValidation:
    def test_missing_title_returns_422(self):
        response = client.post(
            "/triage",
            json={"description": "Some long description here"},
        )
        assert response.status_code == 422
        body = response.json()
        assert body["detail"] == "Invalid ticket input"
        assert len(body["errors"]) > 0

    def test_title_too_short_returns_422(self):
        response = client.post(
            "/triage",
            json={"title": "ab", "description": "Some long description here"},
        )
        assert response.status_code == 422
        body = response.json()
        assert body["detail"] == "Invalid ticket input"

    def test_description_too_short_returns_422(self):
        response = client.post(
            "/triage",
            json={"title": "Valid title", "description": "short"},
        )
        assert response.status_code == 422
        body = response.json()
        assert body["detail"] == "Invalid ticket input"

    def test_empty_body_returns_422(self):
        response = client.post("/triage", json={})
        assert response.status_code == 422

    def test_missing_description_returns_422(self):
        response = client.post(
            "/triage",
            json={"title": "Valid title"},
        )
        assert response.status_code == 422
        body = response.json()
        assert body["detail"] == "Invalid ticket input"
        assert len(body["errors"]) > 0


class TestTriageEndpointFallback:
    @patch("app.triage_service.triage_ticket_raw")
    def test_model_failure_returns_200_with_fallback(self, mock_raw):
        mock_raw.side_effect = APITimeoutError(request=MagicMock())
        response = client.post(
            "/triage",
            json={
                "title": "Cannot access account",
                "description": "I am unable to log in to my account since this morning.",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["confidence"] == 0.0
        assert body["category"] == "other"
        assert body["recommended_team"] == "support"


class TestSuccessfulTriageFlow:
    @patch("app.triage_service.triage_ticket_raw")
    def test_valid_request_returns_200_with_full_result(self, mock_raw):
        mock_raw.return_value = json.dumps(
            {
                "category": "technical_issue",
                "priority": "high",
                "sentiment": "frustrated",
                "recommended_team": "engineering",
                "short_summary": "User cannot log in to the dashboard.",
                "suggested_reply": "We are looking into this issue.",
                "confidence": 0.92,
                "needs_escalation": False,
            }
        )
        response = client.post(
            "/triage",
            json={
                "title": "Cannot access account",
                "description": "I am unable to log in to my account since this morning.",
                "customer_tier": "standard",
                "product_name": "Dashboard",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == "technical_issue"
        assert body["priority"] == "high"
        assert body["sentiment"] == "frustrated"
        assert body["recommended_team"] == "engineering"
        assert body["confidence"] == 0.92
        assert body["needs_escalation"] is False
        assert isinstance(body["short_summary"], str)
        assert isinstance(body["suggested_reply"], str)

    @patch("app.triage_service.triage_ticket_raw")
    def test_outage_ticket_triggers_escalation_rule(self, mock_raw):
        mock_raw.return_value = json.dumps(
            {
                "category": "outage",
                "priority": "high",
                "sentiment": "angry",
                "recommended_team": "sre_ops",
                "short_summary": "Complete service outage reported.",
                "suggested_reply": "Our team is investigating immediately.",
                "confidence": 0.98,
                "needs_escalation": False,
            }
        )
        response = client.post(
            "/triage",
            json={
                "title": "Everything is down",
                "description": "All our services stopped responding 20 minutes ago.",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == "outage"
        assert body["needs_escalation"] is True

    @patch("app.triage_service.triage_ticket_raw")
    def test_valid_request_without_optional_fields_returns_200(self, mock_raw):
        mock_raw.return_value = json.dumps(
            {
                "category": "billing",
                "priority": "low",
                "sentiment": "calm",
                "recommended_team": "billing_ops",
                "short_summary": "Question about invoice.",
                "suggested_reply": "Please find the invoice details below.",
                "confidence": 0.85,
                "needs_escalation": False,
            }
        )
        response = client.post(
            "/triage",
            json={
                "title": "Invoice question",
                "description": "I have a question about my last invoice amount.",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["category"] == "billing"
        assert body["confidence"] == 0.85
