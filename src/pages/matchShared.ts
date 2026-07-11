import type { MatchPublic } from "../types"

export const inputClass = "bg-gray-800/60 border border-gray-700/70 rounded-lg px-3 py-2.5 text-base text-white w-full focus:outline-none focus-visible:ring-1 focus-visible:ring-[#d4f53c] focus-visible:border-[#d4f53c] transition-colors placeholder-gray-600"
export const labelClass = "text-xs font-semibold uppercase tracking-wide pl-0.5"
export const labelStyle = { color: "rgba(212,245,60,0.7)" }

export const LS_MATCH_FILTER = "padel_match_filter"
export const LS_MATCH_TOKENS = "padel_match_tokens" // slug -> token (own player token or manage_token)

export function getStoredMatchToken(slug: string): string | null {
  try {
    const map = JSON.parse(localStorage.getItem(LS_MATCH_TOKENS) ?? "{}") as Record<string, string>
    return map[slug] ?? null
  } catch { return null }
}

export function storeMatchToken(slug: string, token: string): void {
  try {
    const map = JSON.parse(localStorage.getItem(LS_MATCH_TOKENS) ?? "{}") as Record<string, string>
    map[slug] = token
    localStorage.setItem(LS_MATCH_TOKENS, JSON.stringify(map))
  } catch { /* private-mode Safari */ }
}

// Called after leaving a match, or when a stored token turns out to be
// invalid (e.g. the organizer removed this player) — stops the page from
// silently retrying a dead token on every future visit.
export function clearMatchToken(slug: string): void {
  try {
    const map = JSON.parse(localStorage.getItem(LS_MATCH_TOKENS) ?? "{}") as Record<string, string>
    delete map[slug]
    localStorage.setItem(LS_MATCH_TOKENS, JSON.stringify(map))
  } catch { /* private-mode Safari */ }
}

// ── Formatting ──────────────────────────────────────────────────────────────────

export function formatMatchWhen(startsAt: string, endsAt: string): string {
  const s = new Date(startsAt)
  const e = new Date(endsAt)
  const today = new Date()
  const isToday = s.toDateString() === today.toDateString()
  const tomorrow = new Date(today)
  tomorrow.setDate(today.getDate() + 1)
  const isTomorrow = s.toDateString() === tomorrow.toDateString()
  const dayLabel = isToday ? "Heute" : isTomorrow ? "Morgen"
    : s.toLocaleDateString("de-AT", { weekday: "short", day: "2-digit", month: "2-digit" })
  const fmt = (d: Date) => d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" })
  return `${dayLabel} · ${fmt(s)}–${fmt(e)} Uhr`
}

export function formatPrice(priceTotal: number | null, spotsTotal: number): string {
  if (priceTotal == null) return "Preis noch offen"
  const perPerson = (priceTotal / spotsTotal).toFixed(2).replace(/\.00$/, "").replace(".", ",")
  return `${priceTotal % 1 === 0 ? priceTotal : priceTotal.toFixed(2).replace(".", ",")} € gesamt · ${perPerson} €/Person`
}

export function courtTypeLabel(courtType?: string | null): string {
  if (courtType === "indoor") return "Indoor"
  if (courtType === "outdoor") return "Outdoor"
  if (courtType === "indoor+outdoor") return "Indoor & Outdoor"
  return ""
}

export function occupied(m: Pick<MatchPublic, "players">): number {
  return 1 + m.players.length // organizer always counts as one
}

export function spotsLeftLabel(m: Pick<MatchPublic, "players" | "spots_total">): string {
  const left = m.spots_total - occupied(m)
  if (left <= 0) return "Voll. Der Rest kommt zu spät."
  if (left === 1) return "einer fehlt noch"
  return `${left} fehlen noch`
}

// Converts a date+time picked in the UI (assumed Europe/Vienna wall-clock,
// matching how the Court Finder's own date/time pickers work) into a
// timezone-aware ISO string the backend can compare directly against UTC
// "now" — correct across the CET/CEST DST switch, no date library needed.
function viennaOffset(dateStr: string): string {
  const probe = new Date(`${dateStr}T12:00:00Z`)
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Europe/Vienna", timeZoneName: "shortOffset", hour: "2-digit" }).formatToParts(probe)
  const tzPart = parts.find(p => p.type === "timeZoneName")?.value ?? "GMT+1"
  const m = tzPart.match(/GMT([+-]\d+)/)
  const hours = m ? parseInt(m[1], 10) : 1
  return `${hours >= 0 ? "+" : "-"}${String(Math.abs(hours)).padStart(2, "0")}:00`
}

export function toViennaISO(dateStr: string, timeStr: string): string {
  return `${dateStr}T${timeStr}:00${viennaOffset(dateStr)}`
}

// Reverse of the above — used to prefill the edit form from a stored ISO instant.
export function viennaDateTimeParts(iso: string): { date: string; time: string } {
  const d = new Date(iso)
  const parts = d.toLocaleString("sv-SE", { timeZone: "Europe/Vienna" }).split(" ")
  return { date: parts[0], time: (parts[1] ?? "00:00:00").slice(0, 5) }
}

// ── Level-overestimation remark, shown under the level picker on the create form ──
export const LEVEL_SNARK = "Trag dein echtes Level ein, nicht dein Wunschlevel. Die anderen merken es in den ersten fünf Minuten."
