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
