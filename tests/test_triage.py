import pytest

from app.rules import apply_business_rules
from app.schemas import (
    Sentiment,
    TicketCategory,
    TicketInput,
    TicketPriority,
    TicketTriageResult,
    RecommendedTeam,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(**overrides) -> TicketTriageResult:
    """Return a baseline TicketTriageResult with sensible defaults."""
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
    """Return a baseline TicketInput with sensible defaults."""
    defaults = dict(
        title="Login not working",
        description="User cannot log in to the dashboard.",
        customer_tier="standard",
        product_name="App",
    )
    defaults.update(overrides)
    return TicketInput(**defaults)


# ---------------------------------------------------------------------------
# Rule 1: Outage → force needs_escalation = True
# ---------------------------------------------------------------------------

class TestRule1OutageEscalation:
    def test_outage_sets_escalation(self):
        result = make_result(category=TicketCategory.outage, needs_escalation=False)
        ticket = make_ticket()
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is True

    def test_outage_keeps_escalation_when_already_true(self):
        result = make_result(category=TicketCategory.outage, needs_escalation=True)
        ticket = make_ticket()
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is True

    def test_non_outage_does_not_set_escalation(self):
        for category in [
            TicketCategory.billing,
            TicketCategory.technical_issue,
            TicketCategory.account_access,
            TicketCategory.bug_report,
            TicketCategory.feature_request,
            TicketCategory.cancellation,
            TicketCategory.other,
        ]:
            result = make_result(category=category, needs_escalation=False)
            ticket = make_ticket()
            out = apply_business_rules(result, ticket)
            assert out.needs_escalation is False, f"category={category} unexpectedly escalated"


# ---------------------------------------------------------------------------
# Rule 2: "production down" in title → priority = urgent
# ---------------------------------------------------------------------------

class TestRule2ProductionDown:
    def test_exact_phrase_sets_urgent(self):
        result = make_result(priority=TicketPriority.medium)
        ticket = make_ticket(title="production down since 2am")
        out = apply_business_rules(result, ticket)
        assert out.priority == TicketPriority.urgent

    def test_phrase_case_insensitive_uppercase(self):
        result = make_result(priority=TicketPriority.low)
        ticket = make_ticket(title="PRODUCTION DOWN right now")
        out = apply_business_rules(result, ticket)
        assert out.priority == TicketPriority.urgent

    def test_phrase_case_insensitive_mixed(self):
        result = make_result(priority=TicketPriority.high)
        ticket = make_ticket(title="Production Down in EU region")
        out = apply_business_rules(result, ticket)
        assert out.priority == TicketPriority.urgent

    def test_already_urgent_stays_urgent(self):
        result = make_result(priority=TicketPriority.urgent)
        ticket = make_ticket(title="production down emergency")
        out = apply_business_rules(result, ticket)
        assert out.priority == TicketPriority.urgent

    def test_unrelated_title_does_not_bump_priority(self):
        result = make_result(priority=TicketPriority.low)
        ticket = make_ticket(title="Cannot reset my password")
        out = apply_business_rules(result, ticket)
        assert out.priority == TicketPriority.low

    def test_partial_phrase_does_not_trigger(self):
        result = make_result(priority=TicketPriority.medium)
        ticket = make_ticket(title="production issue reported")
        out = apply_business_rules(result, ticket)
        assert out.priority == TicketPriority.medium


# ---------------------------------------------------------------------------
# Rule 3: Enterprise + angry + high priority → needs_escalation = True
# ---------------------------------------------------------------------------

class TestRule3EnterpriseAngryHigh:
    def test_triggers_when_all_conditions_met(self):
        result = make_result(
            sentiment=Sentiment.angry,
            priority=TicketPriority.high,
            needs_escalation=False,
        )
        ticket = make_ticket(customer_tier="enterprise")
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is True

    def test_does_not_trigger_non_enterprise(self):
        for tier in ["standard", "free", "premium", None]:
            result = make_result(
                sentiment=Sentiment.angry,
                priority=TicketPriority.high,
                needs_escalation=False,
            )
            ticket = make_ticket(customer_tier=tier)
            out = apply_business_rules(result, ticket)
            assert out.needs_escalation is False, f"tier={tier!r} unexpectedly escalated"

    def test_does_not_trigger_non_angry_sentiment(self):
        for sentiment in [Sentiment.calm, Sentiment.frustrated, Sentiment.neutral]:
            result = make_result(
                sentiment=sentiment,
                priority=TicketPriority.high,
                needs_escalation=False,
            )
            ticket = make_ticket(customer_tier="enterprise")
            out = apply_business_rules(result, ticket)
            assert out.needs_escalation is False, f"sentiment={sentiment} unexpectedly escalated"

    def test_does_not_trigger_non_high_priority(self):
        for priority in [TicketPriority.low, TicketPriority.medium, TicketPriority.urgent]:
            result = make_result(
                sentiment=Sentiment.angry,
                priority=priority,
                needs_escalation=False,
            )
            ticket = make_ticket(customer_tier="enterprise")
            out = apply_business_rules(result, ticket)
            assert out.needs_escalation is False, f"priority={priority} unexpectedly escalated"


# ---------------------------------------------------------------------------
# Rule 4: Low confidence (< 0.65) → needs_escalation = True
# ---------------------------------------------------------------------------

class TestRule4LowConfidence:
    def test_confidence_below_threshold_sets_escalation(self):
        result = make_result(confidence=0.64, needs_escalation=False)
        ticket = make_ticket()
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is True

    def test_confidence_at_threshold_does_not_escalate(self):
        result = make_result(confidence=0.65, needs_escalation=False)
        ticket = make_ticket()
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is False

    def test_confidence_above_threshold_does_not_escalate(self):
        result = make_result(confidence=0.9, needs_escalation=False)
        ticket = make_ticket()
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is False

    def test_zero_confidence_sets_escalation(self):
        result = make_result(confidence=0.0, needs_escalation=False)
        ticket = make_ticket()
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is True

    def test_low_confidence_keeps_escalation_when_already_true(self):
        result = make_result(confidence=0.5, needs_escalation=True)
        ticket = make_ticket()
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is True


# ---------------------------------------------------------------------------
# Combined / edge cases
# ---------------------------------------------------------------------------

class TestCombinedRules:
    def test_outage_and_enterprise_angry_high_both_escalate(self):
        """Both rule 1 and rule 3 should fire; result must have escalation and
        the priority must be unchanged (no 'production down' in title)."""
        result = make_result(
            category=TicketCategory.outage,
            sentiment=Sentiment.angry,
            priority=TicketPriority.high,
            needs_escalation=False,
        )
        ticket = make_ticket(customer_tier="enterprise")
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is True
        assert out.priority == TicketPriority.high  # rule 2 did NOT fire

    def test_outage_and_production_down_title(self):
        """Rule 1 forces escalation and rule 2 bumps priority to urgent."""
        result = make_result(
            category=TicketCategory.outage,
            priority=TicketPriority.high,
            needs_escalation=False,
        )
        ticket = make_ticket(title="production down - all services affected")
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is True
        assert out.priority == TicketPriority.urgent

    def test_all_three_rules_fire(self):
        """Outage + 'production down' title + enterprise angry high → all three rules apply."""
        result = make_result(
            category=TicketCategory.outage,
            sentiment=Sentiment.angry,
            priority=TicketPriority.high,
            needs_escalation=False,
        )
        ticket = make_ticket(
            title="production down for enterprise customer",
            customer_tier="enterprise",
        )
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is True
        assert out.priority == TicketPriority.urgent

    def test_no_rules_fire_baseline(self):
        """A boring ticket with no special conditions should pass through unchanged."""
        result = make_result(
            category=TicketCategory.billing,
            sentiment=Sentiment.calm,
            priority=TicketPriority.low,
            needs_escalation=False,
        )
        ticket = make_ticket(
            title="Invoice question",
            customer_tier="free",
        )
        out = apply_business_rules(result, ticket)
        assert out.needs_escalation is False
        assert out.priority == TicketPriority.low
        assert out.category == TicketCategory.billing

    def test_result_is_immutable_original_unchanged(self):
        """apply_business_rules should not mutate the original result object."""
        result = make_result(
            category=TicketCategory.outage,
            priority=TicketPriority.medium,
            needs_escalation=False,
        )
        ticket = make_ticket(title="production down now")
        original_escalation = result.needs_escalation
        original_priority = result.priority
        apply_business_rules(result, ticket)
        assert result.needs_escalation == original_escalation
        assert result.priority == original_priority