TICKET_TRIAGE_SCHEMA = {
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
