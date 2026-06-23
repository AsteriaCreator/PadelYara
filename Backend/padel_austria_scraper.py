"""
Scraper for https://padel-austria.at/tournaments

Paginates through all pages, parses tournament rows, and returns
normalized tournament dicts ready for MongoDB upsert.
"""

import re
import time
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

SOURCE = "padel_austria"
BASE_URL = "https://padel-austria.at"
TOURNAMENTS_URL = f"{BASE_URL}/tournaments"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-AT,de;q=0.9",
}

# Maps page text → internal status values
_STATUS_MAP = {
    "Anmelden": "open",
    "Anmeldung geschlossen": "closed",
    "Abgesagt": "cancelled",
    "Noch nicht offen": "not_open_yet",
}

# Austrian day abbreviations on the site
_WEEKDAY_MAP = {
    "Mo.": "Montag",
    "Di.": "Dienstag",
    "Mi.": "Mittwoch",
    "Do.": "Donnerstag",
    "Fr.": "Freitag",
    "Sa.": "Samstag",
    "So.": "Sonntag",
}


def _parse_date(date_str: str) -> datetime | None:
    """Parse 'Fr. 05.06.2026' or '05.06.2026' → UTC datetime at 00:00."""
    # Strip weekday prefix like "Fr. "
    date_str = re.sub(r"^[A-Za-z]+\.\s*", "", date_str.strip())
    try:
        return datetime.strptime(date_str, "%d.%m.%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_datetime(date_str: str, time_str: str) -> datetime | None:
    """Parse 'Fr. 05.06.2026' + '15:00' → UTC datetime."""
    date_only = re.sub(r"^[A-Za-z]+\.\s*", "", date_str.strip())
    try:
        dt = datetime.strptime(f"{date_only} {time_str.strip()}", "%d.%m.%Y %H:%M")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_detail_datetime(value: str) -> datetime | None:
    """Parse a detail-table value like '21.05.2026, 12:00 Uhr' → UTC datetime."""
    cleaned = value.replace("Uhr", "").strip().rstrip(",").strip()
    try:
        return datetime.strptime(cleaned, "%d.%m.%Y, %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# Detail-page "Turnierinformationen" table labels → tournament dict keys.
# Only the registration window: it's the authoritative source for when a
# tournament became available, which drives the "NEU"/"öffnet bald" labels.
# We deliberately do NOT take Startzeit/Endzeit here — the list page already
# parses the full (possibly multi-day) date range, and the detail table's single
# start/end pair would clobber a multi-day range with one day.
_DETAIL_LABELS = {
    "Registrierung Start": "registration_opens_at",
    "Registrierung Ende": "registration_closes_at",
}


def _parse_detail(soup: BeautifulSoup) -> dict[str, Any]:
    """
    Parse the 'Turnierinformationen' table on a tournament detail page.
    Returns only the date fields it successfully parsed (missing/garbled
    values are omitted so they never overwrite good data on upsert).
    """
    out: dict[str, Any] = {}
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) != 2:
            continue
        field = _DETAIL_LABELS.get(cells[0].get_text(strip=True))
        if not field:
            continue
        dt = _parse_detail_datetime(cells[1].get_text(strip=True))
        if dt:
            out[field] = dt
    return out


def _parse_participants(text: str) -> tuple[int, int, int]:
    """
    Parse '16/16 (2)' → (current=16, max=16, waitlist=2).
    Returns (0, 0, 0) on failure.
    """
    m = re.match(r"(\d+)/(\d+)(?:\s*\((\d+)\))?", text.strip())
    if not m:
        return 0, 0, 0
    current = int(m.group(1))
    maximum = int(m.group(2))
    waitlist = int(m.group(3)) if m.group(3) else 0
    return current, maximum, waitlist


def _parse_row(row) -> dict[str, Any] | None:
    """Parse a single .row.g-2 tournament element into a normalized dict."""
    # Title + source_id from the h5 link
    title_link = row.select_one("h5 a")
    if not title_link:
        return None

    href = title_link.get("href", "")
    source_id_match = re.search(r"/ranked/tournaments/([a-f0-9-]+)", href)
    if not source_id_match:
        return None

    source_id = source_id_match.group(1)
    title = title_link.get_text(strip=True)
    source_url = f"{BASE_URL}{href}"

    # All text nodes in the row — used to extract remaining fields
    all_texts = [t.strip() for t in row.find_all(string=True) if t.strip()]

    # Venue: first <a href="/locations/...">
    venue_link = row.select_one('a[href*="/locations/"]')
    venue_name = venue_link.get_text(strip=True) if venue_link else ""

    # Bundesland: text immediately after venue link, starts with "- "
    bundesland = ""
    if venue_link:
        next_sib = venue_link.next_sibling
        if next_sib:
            bl = str(next_sib).strip()
            bundesland = bl.lstrip("- ").strip()

    # Date spans — collect all span texts that look like dates or times
    date_spans = []
    for span in row.find_all("span"):
        t = span.get_text(strip=True)
        if t and t not in (",", "-"):
            date_spans.append(t)

    # Try to find starts_at: first date+time pair in spans
    starts_at = None
    ends_at = None
    weekday = ""
    if len(date_spans) >= 2:
        # spans: ['Fr. 05.06.2026', '15:00', 'So. 07.06.2026', '15:00'] (multi-day)
        # or:    ['Sa. 06.06.2026', '09:00'] (single day)
        for i, s in enumerate(date_spans):
            if re.match(r"[A-Za-z]+\.", s):  # weekday prefix → date
                if starts_at is None and i + 1 < len(date_spans):
                    starts_at = _parse_datetime(s, date_spans[i + 1])
                    # Extract weekday abbreviation
                    wday_abbr = s.split(".")[0] + "."
                    weekday = _WEEKDAY_MAP.get(wday_abbr, "")
                elif starts_at is not None and i + 1 < len(date_spans):
                    ends_at = _parse_datetime(s, date_spans[i + 1])
                    break

    # Competition - Category: e.g. "Herren - Elite" or "Offener Bewerb - Starter"
    competition = ""
    category = ""
    comp_cat_pattern = re.compile(
        r"^(Herren|Damen|Mixed|Jugend|Offener Bewerb|Juxturnier)\s*-\s*"
        r"(Starter|Advanced|Expert|Professional|Elite|Juxturnier)$"
    )
    for t in all_texts:
        m = comp_cat_pattern.match(t)
        if m:
            competition = m.group(1)
            category = m.group(2)
            break

    # Newcomer override: if title contains "newcomer" (case-insensitive),
    # treat category as "Newcomer" (sub-type of Starter skill level).
    if "newcomer" in title.lower():
        category = "Newcomer"

    # Participants: "X/Y" or "X/Y (Z)"
    participants_current = 0
    participants_max = 0
    participants_waitlist = 0
    for t in all_texts:
        if re.match(r"^\d+/\d+", t):
            participants_current, participants_max, participants_waitlist = _parse_participants(t)
            break

    # Status
    status = "unknown"
    for t in all_texts:
        if t in _STATUS_MAP:
            status = _STATUS_MAP[t]
            break
        # Dynamic "not open yet" text: "Anmeldung öffnet am DD.MM.YYYY, HH:MM Uhr"
        if re.match(r"Anmeldung öffnet am", t):
            status = "not_open_yet"
            break

    # Refine status: if registration is open but tournament is full (no waitlist shown)
    if status == "open" and participants_max > 0 and participants_current >= participants_max:
        status = "full"

    return {
        "source": SOURCE,
        "source_id": source_id,
        "source_url": source_url,
        "title": title,
        "venue_name": venue_name,
        "city": "",           # not available on list page; could be enriched later
        "bundesland": bundesland,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "weekday": weekday,
        "category": category,
        "competition": competition,
        "participants_current": participants_current,
        "participants_max": participants_max,
        "participants_waitlist": participants_waitlist,
        "registration_opens_at": None,   # not shown on list page
        "registration_closes_at": None,  # not shown on list page
        "status": status,
    }


def _fetch_soup(url: str, session: requests.Session) -> BeautifulSoup | None:
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[padel_austria_scraper] Error fetching {url}: {e}")
        return None


def _parse_entries(soup: BeautifulSoup) -> tuple[list[dict], list[dict]]:
    """
    Parse the participant entry tables from a tournament detail page.
    Returns (entries, waitlist_entries).

    The first "Team" table is the regular field; the second (if present) is the
    waitlist. Each row yields:
        {seed, apn, points, player_a_name, player_a_slug, player_b_name, player_b_slug}
    Table headers: # | APN | Punkte | Team
    Each player name in the Team cell links to /players/<slug>.
    """
    def _slug(a) -> str:
        return a["href"].split("/players/")[-1].strip("/")

    def _parse_table(table) -> list[dict]:
        rows_parsed = []
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            seed_text = cells[0].get_text(strip=True).lstrip("#")
            apn_text = cells[1].get_text(strip=True).replace(",", ".")
            points_text = cells[2].get_text(strip=True).replace(".", "").replace(",", "")
            player_links = cells[3].find_all("a", href=re.compile(r"^/players/"))
            if len(player_links) < 2:
                continue
            rows_parsed.append({
                "seed": int(seed_text) if seed_text.isdigit() else None,
                "apn": float(apn_text) if apn_text else None,
                "points": int(points_text) if points_text.isdigit() else None,
                "player_a_name": player_links[0].get_text(strip=True),
                "player_a_slug": _slug(player_links[0]),
                "player_b_name": player_links[1].get_text(strip=True),
                "player_b_slug": _slug(player_links[1]),
            })
        return rows_parsed

    team_tables = [
        t for t in soup.find_all("table")
        if "Team" in [th.get_text(strip=True) for th in t.find_all("th")]
    ]
    entries = _parse_table(team_tables[0]) if len(team_tables) >= 1 else []
    waitlist_entries = _parse_table(team_tables[1]) if len(team_tables) >= 2 else []
    return entries, waitlist_entries


def _fetch_page(page: int, session: requests.Session) -> BeautifulSoup | None:
    url = TOURNAMENTS_URL if page == 1 else f"{TOURNAMENTS_URL}?page={page}"
    return _fetch_soup(url, session)


def _get_total_pages(soup: BeautifulSoup) -> int:
    """Extract the last page number from pagination links."""
    # Pagination links: <a href="?page=12">12</a>
    max_page = 1
    for a in soup.select('a[href*="page="]'):
        href = a.get("href", "")
        m = re.search(r"page=(\d+)", href)
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page


def scrape_all() -> list[dict[str, Any]]:
    """
    Scrape all tournament pages and return normalized tournament dicts.
    Each dict is ready to be upserted into MongoDB.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    print("[padel_austria_scraper] Fetching page 1 to determine total pages...")
    first_soup = _fetch_page(1, session)
    if not first_soup:
        print("[padel_austria_scraper] Failed to fetch page 1.")
        return []

    total_pages = _get_total_pages(first_soup)
    print(f"[padel_austria_scraper] Total pages: {total_pages}")

    all_tournaments: list[dict] = []
    seen_ids: set[str] = set()

    def _process_soup(soup: BeautifulSoup) -> None:
        rows = soup.select(".row.g-2")
        for row in rows:
            t = _parse_row(row)
            if t and t["source_id"] not in seen_ids:
                seen_ids.add(t["source_id"])
                all_tournaments.append(t)

    _process_soup(first_soup)

    for page in range(2, total_pages + 1):
        time.sleep(0.5)  # be polite
        soup = _fetch_page(page, session)
        if soup:
            _process_soup(soup)
        print(f"[padel_austria_scraper] Page {page}/{total_pages} done. Total so far: {len(all_tournaments)}")

    print(f"[padel_austria_scraper] Scrape complete. {len(all_tournaments)} tournaments found.")

    # Fetch entry lists for open and not_open_yet tournaments (participants registered)
    entry_eligible = [t for t in all_tournaments if t["status"] in ("open", "not_open_yet", "full", "closed")]
    print(f"[padel_austria_scraper] Fetching entry lists for {len(entry_eligible)} tournaments...")
    for i, t in enumerate(entry_eligible):
        time.sleep(0.3)
        detail_soup = _fetch_soup(t["source_url"], session)
        if detail_soup:
            t["entries"], t["waitlist_entries"] = _parse_entries(detail_soup)
        else:
            t["entries"] = []
            t["waitlist_entries"] = []
        if (i + 1) % 10 == 0:
            print(f"[padel_austria_scraper] Entry lists: {i + 1}/{len(entry_eligible)}")

    # Enrich with the registration window from each detail page (the list page
    # doesn't expose it). Skip tournaments whose registration window can no longer
    # matter — closed/cancelled, or already started — to avoid hundreds of
    # pointless requests every run.
    now = datetime.now(timezone.utc)
    to_enrich = [
        t for t in all_tournaments
        if t.get("status") not in ("closed", "cancelled")
        and not (isinstance(t.get("starts_at"), datetime) and t["starts_at"] < now)
    ]
    print(
        f"[padel_austria_scraper] Fetching detail pages for {len(to_enrich)} "
        f"of {len(all_tournaments)} tournaments..."
    )
    for i, t in enumerate(to_enrich):
        time.sleep(0.3)  # be polite
        detail_soup = _fetch_soup(t["source_url"], session)
        if detail_soup:
            t.update(_parse_detail(detail_soup))
        if (i + 1) % 25 == 0:
            print(f"[padel_austria_scraper] Detail {i + 1}/{len(to_enrich)} done.")

    print("[padel_austria_scraper] Detail enrichment complete.")
    return all_tournaments


if __name__ == "__main__":
    results = scrape_all()
    for t in results[:5]:
        print(t)
