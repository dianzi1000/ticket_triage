from enum import Enum
from pydantic import BaseModel, Field


class TicketCategory(str, Enum):
    billing = "billing"
    technical_issue = "technical_issue"
    account_access = "account_access"
    bug_report = "bug_report"
    feature_request = "feature_request"
    outage = "outage"
    cancellation = "cancellation"
    other = "other"


class TicketPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class Sentiment(str, Enum):
    calm = "calm"
    frustrated = "frustrated"
    angry = "angry"
    neutral = "neutral"


class RecommendedTeam(str, Enum):
    support = "support"
    billing_ops = "billing_ops"
    engineering = "engineering"
    srer_ops = "sre_ops"
    account_management = "account_management"


class TicketInput(BaseModel):
    title: str = Field(..., min_length=3)
    description: str = Field(..., min_length=10)
    customer_tier: str | None = None
    product_name: str | None = None


class TicketTriageResult(BaseModel):
    category: TicketCategory
    priority: TicketPriority
    sentiment: Sentiment
    recommended_team: RecommendedTeam
    short_summary: str = Field(..., max_length=200)
    suggested_reply: str = Field(..., max_length=600)
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_escalation: bool