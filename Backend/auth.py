import os
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

_ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
_api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)


async def _require_admin(token: str = Security(_api_key_header)):
    # Constant-time compare to avoid leaking the token via timing.
    if not _ADMIN_TOKEN or not token or not secrets.compare_digest(token, _ADMIN_TOKEN):
        raise HTTPException(status_code=403, detail="Forbidden")
