"""
Shared continuous-block availability helpers.

The booking platforms all answer "is a court free at exactly time T?". Players,
though, usually want to play for a stretch — 1 h, 1.5 h, or 2 h. A court that is
free at 18:00 but booked at 19:00 is useless for a 2 h game even though every
scraper would call it "free".

This module centralises the maths for that. Each scraper reduces its raw data to
a per-court list of BUSY intervals (minutes since midnight) plus the venue's
opening window and booking grid, and these helpers turn that into the set of
bookable durations available starting at a given time. app.py then intersects
that set with the durations the user actually selected.

Caching note: `free_durations` is duration-AGNOSTIC — it lists every duration
that fits at T regardless of what the user picked — so a single cached value per
venue/date/time serves any duration selection. The user's choice is applied only
when the response is assembled.
"""

# Durations the UI offers, in minutes. Keep in sync with the frontend picker.
SELECTABLE_DURATIONS: list[int] = [60, 90, 120]
DEFAULT_DURATIONS:    list[int] = [120]

# Upper bound for continuous-block computation. No point enumerating durations a
# player would never pick; also keeps the lists tiny.
MAX_DURATION_MIN = 120


def parse_durations(raw: str | None) -> list[int]:
    """
    Parse the `durations` query param ("60,90,120") into a sorted, de-duplicated
    list of valid durations. Falls back to DEFAULT_DURATIONS when the param is
    missing, empty, or contains nothing valid.
    """
    if not raw:
        return list(DEFAULT_DURATIONS)
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            v = int(part)
            if v in SELECTABLE_DURATIONS:
                out.append(v)
    return sorted(set(out)) or list(DEFAULT_DURATIONS)


def hhmm_to_min(hhmm: str) -> int:
    """'1830' or '18:30' → minutes since midnight."""
    h = hhmm.replace(":", "")
    return int(h[:2]) * 60 + int(h[2:])


def court_free_durations(
    busy_intervals: list[tuple[int, int]],
    target_min: int,
    grid_min: int,
    open_min: int,
    close_min: int,
) -> list[int]:
    """
    Bookable durations (multiples of `grid_min`) that fit on ONE court starting
    exactly at `target_min`, given that court's busy intervals and the venue's
    opening window [open_min, close_min).

    `close_min` is the time the venue stops play (a game may run right up to it),
    so a block is allowed to END at close_min but not after.

    Returns e.g. [30, 60, 90, 120] for a 30-min-grid court free for 2 h+.
    Empty when the court is busy at target, the start is outside opening hours,
    or the start does not sit on the court's booking grid.
    """
    if grid_min <= 0:
        grid_min = 30

    # Start must be inside opening hours and land on the booking grid. UI starts
    # are on the hour, so this only ever filters sub-hour grids, never the user.
    if target_min < open_min or target_min >= close_min:
        return []
    if (target_min - open_min) % grid_min != 0:
        return []

    # Free runway = distance from target to the first thing that blocks it:
    # the next busy interval that starts at/after target, or closing time.
    limit = close_min
    for bs, be in busy_intervals:
        if bs <= target_min < be:
            return []  # court already occupied at the requested time
        if bs > target_min:
            limit = min(limit, bs)

    free_min = limit - target_min
    durations: list[int] = []
    k = 1
    while k * grid_min <= free_min and k * grid_min <= MAX_DURATION_MIN:
        durations.append(k * grid_min)
        k += 1
    return durations


def venue_free_durations(
    courts_busy: dict[str, list[tuple[int, int]]],
    target_min: int,
    grid_min: int,
    open_min: int,
    close_min: int,
) -> list[int]:
    """
    Union of bookable durations across all courts at a venue. A duration counts
    as available if ANY single court can host it continuously from target.
    """
    available: set[int] = set()
    for busy in courts_busy.values():
        available.update(
            court_free_durations(busy, target_min, grid_min, open_min, close_min)
        )
    return sorted(available)


def match_durations(free_durations: list[int], wanted: list[int]) -> list[int]:
    """Durations the user wants that are actually available, longest first."""
    free = set(free_durations)
    return sorted((d for d in wanted if d in free), reverse=True)


def durations_from_available_starts(
    available_starts: list[int],
    target: int,
    step_sec: int = 1800,
    max_min: int = MAX_DURATION_MIN,
) -> list[int]:
    """
    For platforms that expose AVAILABLE slot starts directly (eTennis: one free
    cell per bookable start, in seconds), the bookable durations on ONE court
    starting at `target` are k consecutive free cells: a block of k*step is
    bookable iff cells target, target+step, …, target+(k-1)*step are all free.

    `available_starts` are Unix timestamps (seconds); `target` likewise. Returns
    durations in MINUTES (multiples of step). Empty when the target cell itself
    isn't free.
    """
    if step_sec <= 0:
        step_sec = 1800
    starts = set(available_starts)
    if target not in starts:
        return []
    durations: list[int] = []
    k = 1
    while True:
        dur_min = (k * step_sec) // 60
        if dur_min > max_min:
            break
        if all((target + i * step_sec) in starts for i in range(k)):
            durations.append(dur_min)
            k += 1
        else:
            break
    return durations
