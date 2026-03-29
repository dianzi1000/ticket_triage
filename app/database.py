import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

from app.schemas import TicketInput, TicketTriageResult

logger = logging.getLogger(__name__)

_DB_PATH_ENV = "TRIAGE_DB_PATH"
_DEFAULT_DB_PATH = "triage.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS triage_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL,
    customer_tier TEXT,
    product_name  TEXT,
    model_result  TEXT    NOT NULL,
    final_result  TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
)
"""


def _db_path() -> str:
    return os.getenv(_DB_PATH_ENV, _DEFAULT_DB_PATH)


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the triage_results table if it does not already exist."""
    with _get_connection() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    logger.info("database_initialized", extra={"db_path": _db_path()})


def save_triage_result(
    ticket: TicketInput,
    model_result: TicketTriageResult,
    final_result: TicketTriageResult,
) -> None:
    """Persist one triage record to SQLite."""
    created_at = datetime.now(timezone.utc).isoformat()
    try:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO triage_results
                    (title, description, customer_tier, product_name,
                     model_result, final_result, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket.title,
                    ticket.description,
                    ticket.customer_tier,
                    ticket.product_name,
                    model_result.model_dump_json(),
                    final_result.model_dump_json(),
                    created_at,
                ),
            )
            conn.commit()
    except sqlite3.Error as exc:
        logger.error("db_save_failed", extra={"error": str(exc)})
