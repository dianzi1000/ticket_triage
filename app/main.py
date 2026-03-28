from fastapi import FastAPI
from app.schemas import TicketInput, TicketTriageResult
from app.triage_service import triage_ticket

app = FastAPI(title="Ticket Triage Service")


@app.post("/triage", response_model=TicketTriageResult)
def triage(ticket: TicketInput) -> TicketTriageResult:
    return triage_ticket(ticket)