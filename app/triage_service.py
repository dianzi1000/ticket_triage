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
    """Lazily initialize the OpenAI client so import succeeds without a key."""
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


def _classify_ticket(ticket: TicketInput) -> TicketTriageResult:
    """Call the AI model and validate the response, returning a result or fallback."""
    try:
        raw_json = triage_ticket_raw(ticket)
    except APITimeoutError:
        logger.error("OpenAI API call timed out after %ss", MODEL_TIMEOUT_SECONDS)
        return fallback_result("model timeout")
    except APIError as exc:
        logger.error("OpenAI API error: %s", exc)
        return fallback_result("model error")
    except Exception as exc:
        logger.exception("Unexpected error during model call: %s", exc)
        return fallback_result("unexpected error")

    logger.info("ai_response_received", extra={"response_length": len(raw_json)})

    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Failed to parse model response as JSON: %s", exc)
        return fallback_result("invalid model response")

    try:
        result = TicketTriageResult.model_validate(data)
    except ValidationError as exc:
        logger.error(
            "validation_failure",
            extra={"error_count": exc.error_count()},
        )
        return fallback_result("validation error")

    logger.info(
        "validation_success",
        extra={
            "category": result.category,
            "priority": result.priority,
            "confidence": result.confidence,
        },
    )
    return result


def triage_ticket(ticket: TicketInput) -> TicketTriageResult:
    result = apply_business_rules(_classify_ticket(ticket), ticket)
    logger.info(
        "triage_complete",
        extra={
            "category": result.category,
            "priority": result.priority,
            "needs_escalation": result.needs_escalation,
            "recommended_team": result.recommended_team,
            "confidence": result.confidence,
        },
    )
    return result