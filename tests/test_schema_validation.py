import pytest
from pydantic import ValidationError

from app.schemas import (
    RecommendedTeam,
    Sentiment,
    TicketCategory,
    TicketInput,
    TicketPriority,
    TicketTriageResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_valid_result(**overrides) -> dict:
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
    return defaults


# ---------------------------------------------------------------------------
# TicketInput schema validation
# ---------------------------------------------------------------------------

class TestTicketInputSchema:
    def test_valid_with_all_fields(self):
        ticket = TicketInput(
            title="Login broken",
            description="User cannot log in since this morning.",
            customer_tier="enterprise",
            product_name="Dashboard",
        )
        assert ticket.title == "Login broken"
        assert ticket.customer_tier == "enterprise"

    def test_valid_with_only_required_fields(self):
        ticket = TicketInput(
            title="Login broken",
            description="User cannot log in since this morning.",
        )
        assert ticket.customer_tier is None
        assert ticket.product_name is None

    def test_title_at_minimum_length_is_valid(self):
        ticket = TicketInput(title="abc", description="Ten chars!!!")
        assert ticket.title == "abc"

    def test_title_below_minimum_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            TicketInput(title="ab", description="Ten chars!!!")
        assert "title" in str(exc_info.value)

    def test_description_at_minimum_length_is_valid(self):
        ticket = TicketInput(title="Valid title", description="1234567890")
        assert ticket.description == "1234567890"

    def test_description_below_minimum_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            TicketInput(title="Valid title", description="123456789")
        assert "description" in str(exc_info.value)

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            TicketInput(description="Ten chars!!!")

    def test_missing_description_raises(self):
        with pytest.raises(ValidationError):
            TicketInput(title="Valid title")


# ---------------------------------------------------------------------------
# TicketTriageResult schema validation
# ---------------------------------------------------------------------------

class TestTicketTriageResultSchema:
    def test_valid_instantiation(self):
        result = TicketTriageResult(**make_valid_result())
        assert result.category == TicketCategory.technical_issue
        assert result.confidence == 0.9
        assert result.needs_escalation is False

    def test_confidence_at_zero_is_valid(self):
        result = TicketTriageResult(**make_valid_result(confidence=0.0))
        assert result.confidence == 0.0

    def test_confidence_at_one_is_valid(self):
        result = TicketTriageResult(**make_valid_result(confidence=1.0))
        assert result.confidence == 1.0

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            TicketTriageResult(**make_valid_result(confidence=-0.1))
        assert "confidence" in str(exc_info.value)

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            TicketTriageResult(**make_valid_result(confidence=1.1))
        assert "confidence" in str(exc_info.value)

    def test_short_summary_at_max_length_is_valid(self):
        result = TicketTriageResult(**make_valid_result(short_summary="x" * 200))
        assert len(result.short_summary) == 200

    def test_short_summary_exceeding_max_length_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            TicketTriageResult(**make_valid_result(short_summary="x" * 201))
        assert "short_summary" in str(exc_info.value)

    def test_suggested_reply_at_max_length_is_valid(self):
        result = TicketTriageResult(**make_valid_result(suggested_reply="x" * 600))
        assert len(result.suggested_reply) == 600

    def test_suggested_reply_exceeding_max_length_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            TicketTriageResult(**make_valid_result(suggested_reply="x" * 601))
        assert "suggested_reply" in str(exc_info.value)

    def test_invalid_category_raises(self):
        with pytest.raises(ValidationError):
            TicketTriageResult(**make_valid_result(category="not_a_category"))

    def test_invalid_priority_raises(self):
        with pytest.raises(ValidationError):
            TicketTriageResult(**make_valid_result(priority="super_urgent"))

    def test_invalid_sentiment_raises(self):
        with pytest.raises(ValidationError):
            TicketTriageResult(**make_valid_result(sentiment="ecstatic"))

    def test_invalid_recommended_team_raises(self):
        with pytest.raises(ValidationError):
            TicketTriageResult(**make_valid_result(recommended_team="unknown_team"))

    def test_all_category_enum_values_are_valid(self):
        for category in TicketCategory:
            result = TicketTriageResult(**make_valid_result(category=category))
            assert result.category == category

    def test_all_priority_enum_values_are_valid(self):
        for priority in TicketPriority:
            result = TicketTriageResult(**make_valid_result(priority=priority))
            assert result.priority == priority

    def test_all_sentiment_enum_values_are_valid(self):
        for sentiment in Sentiment:
            result = TicketTriageResult(**make_valid_result(sentiment=sentiment))
            assert result.sentiment == sentiment

    def test_all_recommended_team_values_are_valid(self):
        for team in RecommendedTeam:
            result = TicketTriageResult(**make_valid_result(recommended_team=team))
            assert result.recommended_team == team
