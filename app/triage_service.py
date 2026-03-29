import json
import logging
import os

from dotenv import load_dotenv
from openai import APITimeoutError, APIError, OpenAI
from pydantic import ValidationError

from app.prompts import SYSTEM_PROMPT
from app.response_schemas import TICKET_TRIAGE_SCHEMA
from app.rules import apply_business_rules
from app.schemas import (
    TicketCategory,
    TicketInput,
    TicketPriority,
    TicketTriageResult,
    RecommendedTeam,
    Sentiment,
)

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_TIMEOUT_SECONDS = 30

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Lazily initialise the OpenAI client so import succeeds without a key."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is not set"
            )
        _client = OpenAI(api_key=api_key)
    return _client


def build_user_prompt(ticket: TicketInput) -> str:
    return f"""
Ticket Title:
{ticket.title}

Ticket Description:
{ticket.description}

Customer Tier:
{ticket.customer_tier or "unknown"}

Product Name:
{ticket.product_name or "unknown"}
""".strip()


def fallback_result(reason: str) -> TicketTriageResult:
    """Return a safe default triage result when the model call fails."""
    return TicketTriageResult(
        category=TicketCategory.other,
        priority=TicketPriority.medium,
        sentiment=Sentiment.neutral,
        recommended_team=RecommendedTeam.support,
        short_summary=f"Automated triage unavailable: {reason}",
        suggested_reply="Thank you for reaching out. Your ticket has been received and a support agent will review it shortly.",
        confidence=0.0,
        needs_escalation=False,
    )


def triage_ticket_raw(ticket: TicketInput) -> str:
    response = _get_client().responses.create(
        model="gpt-5.4-mini",
        instructions=SYSTEM_PROMPT,
        input=build_user_prompt(ticket),
        text={"format": TICKET_TRIAGE_SCHEMA},
        timeout=MODEL_TIMEOUT_SECONDS,
    )
    return response.output_text


def triage_ticket(ticket: TicketInput) -> TicketTriageResult:
    try:
        raw_json = triage_ticket_raw(ticket)
    except APITimeoutError:
        logger.error("OpenAI API call timed out after %ss", MODEL_TIMEOUT_SECONDS)
        return apply_business_rules(fallback_result("model timeout"), ticket)
    except APIError as exc:
        logger.error("OpenAI API error: %s", exc)
        return apply_business_rules(fallback_result("model error"), ticket)
    except Exception as exc:
        logger.exception("Unexpected error during model call: %s", exc)
        return apply_business_rules(fallback_result("unexpected error"), ticket)

    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Failed to parse model response as JSON: %s", exc)
        return apply_business_rules(fallback_result("invalid model response"), ticket)

    try:
        result = TicketTriageResult.model_validate(data)
    except ValidationError as exc:
        logger.error("Model response failed validation: %s", exc)
        return apply_business_rules(fallback_result("validation error"), ticket)

    return apply_business_rules(result, ticket)