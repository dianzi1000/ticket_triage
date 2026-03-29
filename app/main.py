import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.logging_config import configure_logging
from app.database import init_db
from app.schemas import TicketInput, TicketTriageResult
from app.triage_service import triage_ticket

configure_logging()
init_db()
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
    logger.warning(
        "input_validation_failed",
        extra={"path": request.url.path, "errors": errors},
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


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/triage", response_model=TicketTriageResult)
def triage(ticket: TicketInput) -> TicketTriageResult:
    logger.info(
        "incoming_request",
        extra={
            "ticket_title": ticket.title[:120],
            "customer_tier": ticket.customer_tier,
            "product_name": ticket.product_name,
            "description_length": len(ticket.description),
        },
    )
    start = time.perf_counter()
    result = triage_ticket(ticket)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info("request_complete", extra={"duration_ms": duration_ms})
    return result