"""
Scraper + analysis for a padel-austria.at player profile (Yaras Urteil).

Same access pattern as padel_austria_scraper.py: plain requests + a browser
User-Agent + BeautifulSoup (no auth, no headless browser needed).

`analyze_player(slug)` returns a `facts` dict of DERIVED insights (things the APU
page does not show directly) that gets handed to yara_urteil_prompt.generate_urteil.

Score formats on the site are messy (tiebreaks shown merged, e.g. "77"/"64";
super-tiebreaks like "68 6 10" / "710 0 8"). We decide each match per-column by
the larger integer, then majority of columns wins — verified against the
profile's official won/lost header totals.
"""

import re
import sys
from collections import Counter, defaultdict
from typing import Any

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://padel-austria.at"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-AT,de;q=0.9",
}

# Recency window meta-rule: fetch newest-first up to this many match pages.
MAX_MATCH_PAGES = 3

_DATE_LINE = re.compile(r"^(Mo|Di|Mi|Do|Fr|Sa|So)\.\s*\d{2}\.\d{2}\.\d{4}")
_SCORE_TOKEN = re.compile(r"^(?:\d{1,3}|-)$")


def _fetch(url: str, session: requests.Session) -> BeautifulSoup | None:
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[padel_austria_player] fetch error {url}: {e}")
        return None


def _competition(title: str) -> str:
    """Infer the gender bracket from the tournament title."""
    t = title.lower()
    if "newcomer" in t or "new comer" in t:
        return "Newcomer"
    if "damen" in t:
        return "Damen"
    if "herren" in t:
        return "Herren"
    if "mixed" in t or "mix " in t or "mix-" in t:
        return "Mixed"
    return "Offen"


def _parse_header(text: str) -> dict[str, Any]:
    def grab(pattern: str, cast=str):
        m = re.search(pattern, text)
        if not m:
            return None
        try:
            return cast(m.group(1))
        except ValueError:
            return None

    name_m = re.search(r"^(.+?)\s*\(#(\d+)\)", text, re.MULTILINE)
    return {
        "name": name_m.group(1).strip() if name_m else None,
        "id": name_m.group(2) if name_m else None,
        "rank": grab(r"Platz:\s*(\d+)", int),
        "points": grab(r"Punkte:\s*(\d+)", int),
        "apn": grab(r"APN\s+([\d.,]+)"),
        "matches_played": grab(r"Matches Gespielt\s+(\d+)", int),
        "matches_won": grab(r"Matches Gewonnen\s+(\d+)", int),
        "matches_lost": grab(r"Matches Verloren\s+(\d+)", int),
        "effectiveness": grab(r"Effektivität\s+([\d,]+)\s*%"),
    }


def _parse_points_table(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """The 'Zusammensetzung der Punkte' table: Punkte | Datum | Kategorie | Turnier."""
    out: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        header = " ".join(th.get_text(strip=True) for th in table.find_all("th"))
        if "Punkte" not in header or "Turnier" not in header:
            continue
        for tr in table.find_all("tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 4:
                continue
            try:
                pts = int(tds[0])
            except ValueError:
                continue
            title = tds[3]
            out.append(
                {"points": pts, "date": tds[1], "category": tds[2],
                 "title": title, "competition": _competition(title)}
            )
        break
    return out


def _decide_match(scores_a: list[str], scores_b: list[str]) -> bool | None:
    """True if team A won. Per-column larger int wins; majority of columns wins."""
    sets_a = sets_b = 0
    for sa, sb in zip(scores_a, scores_b):
        if not sa.isdigit() or not sb.isdigit():
            continue
        ia, ib = int(sa), int(sb)
        if ia > ib:
            sets_a += 1
        elif ib > ia:
            sets_b += 1
    if sets_a == sets_b:
        return None
    return sets_a > sets_b


def _parse_matches(lines: list[str], player_name: str) -> list[dict[str, Any]]:
    """Parse the rendered match section into per-match records for `player_name`."""
    # Locate the matches section: the standalone "Matches" header that is followed
    # (somewhere) by a date line. Everything from there to the pagination/footer.
    start = None
    for i, ln in enumerate(lines):
        if ln == "Matches" and i + 2 < len(lines):
            start = i + 1
            break
    if start is None:
        return []
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j] in ("Folge uns auf", "‹ Zurück", "Weiter ›"):
            end = j
            break
    seg = lines[start:end]

    # Split into tournament blocks using date lines (title is the line before).
    date_idx = [k for k, ln in enumerate(seg) if _DATE_LINE.match(ln)]
    matches: list[dict[str, Any]] = []
    for n, d in enumerate(date_idx):
        title = seg[d - 1] if d - 1 >= 0 else ""
        body_end = (date_idx[n + 1] - 1) if n + 1 < len(date_idx) else len(seg)
        body = seg[d + 1:body_end]

        # Parse body into teams: [name, name, score, score?, score?]
        teams: list[dict[str, Any]] = []
        names: list[str] = []
        scores: list[str] = []
        for tok in body:
            if _SCORE_TOKEN.match(tok):
                scores.append(tok)
            else:
                # New name encountered after we already had scores -> flush a team.
                if scores:
                    teams.append({"names": names, "scores": scores})
                    names, scores = [], []
                names.append(tok)
        if names or scores:
            teams.append({"names": names, "scores": scores})

        # Pair consecutive teams into matches.
        for t in range(0, len(teams) - 1, 2):
            ta, tb = teams[t], teams[t + 1]
            if player_name in ta["names"]:
                me, opp = ta, tb
            elif player_name in tb["names"]:
                me, opp = tb, ta
            else:
                continue
            partner = next((nm for nm in me["names"] if nm != player_name), None)
            sa = (me["scores"] + ["-", "-", "-"])[:3]
            sb = (opp["scores"] + ["-", "-", "-"])[:3]
            won = _decide_match(sa, sb)
            if won is None:
                continue
            matches.append({
                "title": title,
                "competition": _competition(title),
                "partner": partner,
                "opponents": opp["names"],
                "won": won,
            })
    return matches


def fetch_player(slug: str) -> dict[str, Any] | None:
    """Scrape header + points table + matches (up to the recency window)."""
    session = requests.Session()
    session.headers.update(HEADERS)
    url = f"{BASE_URL}/players/{slug}"
    soup = _fetch(url, session)
    if soup is None:
        return None

    text = soup.get_text(separator="\n")
    header = _parse_header(text)
    if not header.get("name"):
        return None
    points = _parse_points_table(soup)

    # Matches, paginated newest-first. Stop when a page adds nothing new.
    seen: set[tuple] = set()
    all_matches: list[dict[str, Any]] = []
    for page in range(1, MAX_MATCH_PAGES + 1):
        psoup = soup if page == 1 else _fetch(f"{url}?page={page}", session)
        if psoup is None:
            break
        lines = [ln.strip() for ln in psoup.get_text(separator="\n").split("\n") if ln.strip()]
        page_matches = _parse_matches(lines, header["name"])
        added = 0
        for m in page_matches:
            sig = (m["title"], m["partner"], tuple(m["opponents"]), m["won"])
            if sig in seen:
                continue
            seen.add(sig)
            all_matches.append(m)
            added += 1
        if added == 0:
            break

    return {"header": header, "points": points, "matches": all_matches}


def analyze_player(slug: str) -> dict[str, Any] | None:
    """Return the DERIVED facts dict for the verdict generator."""
    data = fetch_player(slug)
    if data is None:
        return None
    header, points, matches = data["header"], data["points"], data["matches"]

    # Partner splits (W/L per partner).
    partners: dict[str, dict[str, int]] = defaultdict(lambda: {"matches": 0, "wins": 0})
    for m in matches:
        if not m["partner"]:
            continue
        partners[m["partner"]]["matches"] += 1
        partners[m["partner"]]["wins"] += 1 if m["won"] else 0
    partner_list = sorted(
        ({"name": n, "matches": v["matches"], "wins": v["wins"],
          "losses": v["matches"] - v["wins"],
          "win_rate": round(100 * v["wins"] / v["matches"]) if v["matches"] else 0}
         for n, v in partners.items()),
        key=lambda p: p["matches"], reverse=True,
    )

    # Format splits (gender bracket: win rate).
    fmt: dict[str, dict[str, int]] = defaultdict(lambda: {"matches": 0, "wins": 0})
    for m in matches:
        fmt[m["competition"]]["matches"] += 1
        fmt[m["competition"]]["wins"] += 1 if m["won"] else 0
    format_list = [
        {"competition": c, "matches": v["matches"], "wins": v["wins"],
         "losses": v["matches"] - v["wins"],
         "win_rate": round(100 * v["wins"] / v["matches"]) if v["matches"] else 0}
        for c, v in fmt.items()
    ]

    # Best results = top tournaments by points. Join partner + category from match/points data.
    partner_by_title: dict[str, str] = {}
    title_partners: dict[str, Counter] = defaultdict(Counter)
    for m in matches:
        if m["partner"]:
            title_partners[m["title"]][m["partner"]] += 1
    for t, c in title_partners.items():
        partner_by_title[t] = c.most_common(1)[0][0]
    category_by_title: dict[str, str] = {p["title"]: p["category"] for p in points}
    best_results = [
        {"points": p["points"], "category": p["category"],
         "competition": p["competition"], "title": p["title"],
         "partner": partner_by_title.get(p["title"])}
        for p in sorted(points, key=lambda x: x["points"], reverse=True)[:3]
    ]

    # Best placement points per format (results-vs-winrate signal).
    best_pts_by_fmt: dict[str, int] = {}
    for p in points:
        best_pts_by_fmt[p["competition"]] = max(best_pts_by_fmt.get(p["competition"], 0), p["points"])

    # Consistency / clutch from the match window.
    per_tournament: dict[str, dict[str, int]] = defaultdict(lambda: {"m": 0, "w": 0})
    for m in matches:
        per_tournament[m["title"]]["m"] += 1
        per_tournament[m["title"]]["w"] += 1 if m["won"] else 0
    collapse_tournaments = sum(1 for v in per_tournament.values() if v["m"] >= 2 and v["w"] == 0)

    # APN context: interpret the player's APN on the 1.0–8.0 scale.
    # Category eligibility thresholds (APU rules, valid from 1.1.2026):
    #   Newcomer ≤1.5 | Starter ≤2.5 | Advanced ≤4.5 | Expert 2.5–5.5
    #   Professional 3.5+ | Elite 3.5+ | Mixed Starter ≤3.0 | Mixed Advanced open
    try:
        apn_val = float(header["apn"].replace(",", "."))
    except (ValueError, AttributeError):
        apn_val = None

    apn_context: dict[str, Any] = {"value": header["apn"]}
    if apn_val is not None:
        eligible = []
        if apn_val <= 1.5:
            eligible.append("Newcomer")
        if apn_val <= 2.5:
            eligible.append("Starter")
        if apn_val <= 4.5:
            eligible.append("Advanced")
        if 2.5 <= apn_val <= 5.5:
            eligible.append("Expert")
        if apn_val >= 3.5:
            eligible.extend(["Professional", "Elite"])
        apn_context["eligible_categories"] = eligible

        # Position within each played category (bottom/mid/top third of the APN range)
        cat_position: dict[str, str] = {}
        if apn_val <= 4.5:  # Advanced: 1.0–4.5 → range width 3.5
            pct = (apn_val - 1.0) / 3.5
            cat_position["Advanced"] = "unteres Drittel" if pct < 0.33 else ("mittleres Drittel" if pct < 0.67 else "oberes Drittel")
        if apn_val <= 2.5:  # Starter: 1.0–2.5 → range width 1.5
            pct = (apn_val - 1.0) / 1.5
            cat_position["Starter"] = "unteres Drittel" if pct < 0.33 else ("mittleres Drittel" if pct < 0.67 else "oberes Drittel")
        if 2.5 <= apn_val <= 5.5:  # Expert: 2.5–5.5 → range width 3.0
            pct = (apn_val - 2.5) / 3.0
            cat_position["Expert"] = "unteres Drittel" if pct < 0.33 else ("mittleres Drittel" if pct < 0.67 else "oberes Drittel")
        apn_context["position_in_category"] = cat_position

    return {
        "player": {"name": header["name"], "rank": header["rank"],
                   "points": header["points"], "apn": header["apn"],
                   "effectiveness": header["effectiveness"]},
        "totals": {"played": header["matches_played"], "won": header["matches_won"],
                   "lost": header["matches_lost"]},
        "window": {"matches_analysed": len(matches),
                   "note": "letzte Matches (neueste zuerst, bis zu 3 Seiten)"},
        "partners": partner_list,
        "formats": format_list,
        "best_results": best_results,
        "best_points_by_format": best_pts_by_fmt,
        "apn_context": apn_context,
        "consistency": {"tournaments_in_window": len(per_tournament),
                        "tournaments_without_a_win": collapse_tournaments},
    }


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "mayer-cornelia"
    import json
    facts = analyze_player(slug)
    print(json.dumps(facts, ensure_ascii=False, indent=2))
