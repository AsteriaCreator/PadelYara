import asyncio
import os

VENUES: list[dict] = []
_ev_ids: list[tuple] = []
_main_loop: asyncio.AbstractEventLoop | None = None


def rss_mb() -> float:
    """Current resident memory of this process in MB (Linux/Railway via /proc).
    Returns -1 where unavailable (e.g. local Windows). Read-only, no deps."""
    try:
        with open("/proc/self/statm") as f:
            resident_pages = int(f.read().split()[1])
        page_size = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
        return resident_pages * page_size / 1_048_576
    except Exception:
        return -1.0
