import os
from dotenv import load_dotenv
from openai import OpenAI
import json

from app.prompts import SYSTEM_PROMPT
from app.rules import apply_business_rules
from app.schemas import TicketInput, TicketTriageResult

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


def triage_ticket_raw(ticket: TicketInput):
    response = client.responses.create(
        model="gpt-5.4-mini",
        instructions=SYSTEM_PROMPT,
        input=build_user_prompt(ticket),
        text={
            "format": {
                "type": "json_schema",
                "name": "ticket_triage_result",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": [
                                "billing",
                                "technical_issue",
                                "account_access",
                                "bug_report",
                                "feature_request",
                                "outage",
                                "cancellation",
                                "other"
                            ]
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "urgent"]
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["calm", "frustrated", "angry", "neutral"]
                        },
                        "recommended_team": {
                            "type": "string",
                            "enum": [
                                "support",
                                "billing_ops",
                                "engineering",
                                "sre_ops",
                                "account_management"
                            ]
                        },
                        "short_summary": {"type": "string"},
                        "suggested_reply": {"type": "string"},
                        "confidence": {"type": "number"},
                        "needs_escalation": {"type": "boolean"}
                    },
                    "required": [
                        "category",
                        "priority",
                        "sentiment",
                        "recommended_team",
                        "short_summary",
                        "suggested_reply",
                        "confidence",
                        "needs_escalation"
                    ]
                },
                "strict": True
            }
        }
    )
    return response.output_text

def triage_ticket(ticket: TicketInput) -> TicketTriageResult:
    raw_json = triage_ticket_raw(ticket)
    data = json.loads(raw_json)
    result = TicketTriageResult.model_validate(data)
    return apply_business_rules(result, ticket)