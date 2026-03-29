import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import TicketInput, TicketTriageResult
from app.triage_service import triage_ticket

logger = logging.getLogger(__name__)

app = FastAPI(title="Ticket Triage Service")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
            }
        )
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid ticket input", "errors": errors},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("Unhandled server error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )


@app.post("/triage", response_model=TicketTriageResult)
def triage(ticket: TicketInput) -> TicketTriageResult:
    return triage_ticket(ticket)