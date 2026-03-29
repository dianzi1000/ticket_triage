from app.schemas import Sentiment, TicketCategory, TicketPriority, TicketTriageResult, TicketInput


def apply_business_rules(result: TicketTriageResult, ticket: TicketInput) -> TicketTriageResult:
    """Apply deterministic post-model business rules to the triage result.

    Rules are evaluated independently and may compound (e.g., an outage ticket
    for an angry enterprise customer at high priority will trigger both rule 1
    and rule 3).
    """
    # Rule 1: Outage → force escalation
    if result.category == TicketCategory.outage:
        result = result.model_copy(update={"needs_escalation": True})

    # Rule 2: "production down" in title → force urgent priority
    if "production down" in ticket.title.lower():
        result = result.model_copy(update={"priority": TicketPriority.urgent})

    # Rule 3: Enterprise + angry + high priority → escalate
    if (
        ticket.customer_tier == "enterprise"
        and result.sentiment == Sentiment.angry
        and result.priority == TicketPriority.high
    ):
        result = result.model_copy(update={"needs_escalation": True})

    # Rule 4: Low confidence → flag for human review
    if result.confidence < 0.65:
        result = result.model_copy(update={"needs_escalation": True})

    # Rule 5: Billing category → route to billing_ops team
    if result.category == TicketCategory.billing:
        result = result.model_copy(update={"recommended_team": RecommendedTeam.billing_ops})

    return result
