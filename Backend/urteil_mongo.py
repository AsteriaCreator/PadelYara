"""
Storage for Yaras Urteil requests + generated verdicts.

Every /api/urteil call is logged to padel_checker.urteil_log so there is a record
of what Yara said about whom (in case someone complains). Best-effort: logging
never raises, so it can't break the response.
"""

import os
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

_client: AsyncIOMotorClient | None = None


def _get_db():
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI", "")
        if not uri:
            raise RuntimeError("MONGODB_URI not set")
        _client = AsyncIOMotorClient(uri)
    return _client["padel_checker"]


async def log_urteil(entry: dict[str, Any]) -> None:
    """Insert one verdict record. Swallows all errors — logging is non-critical."""
    try:
        db = _get_db()
        await db["urteil_log"].insert_one(
            {**entry, "created_at": datetime.now(timezone.utc)}
        )
    except Exception as e:
        print(f"[urteil_mongo] log failed: {e}")
