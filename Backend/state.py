import asyncio

VENUES: list[dict] = []
_ev_ids: list[tuple] = []
_main_loop: asyncio.AbstractEventLoop | None = None
