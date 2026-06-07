import type { Tournament } from "./types"

const DAY_MS = 24 * 60 * 60 * 1000
const DAYS_NEW = 7
const DAYS_SOON = 7

// True if `iso` is in the past but within the last `days` days.
function withinPast(iso: string | null, days: number): boolean {
  if (!iso) return false
  const diffMs = Date.now() - new Date(iso).getTime()
  return diffMs >= 0 && diffMs < days * DAY_MS
}

// "NEU" — newly added to our listing (first_seen_at, which an organizer can't
// backdate), OR registration just opened. Both matter: a tournament posted today
// with a backdated registration date is still new to us, and a long-listed
// tournament whose registration just opened is newly actionable.
export function isNew(t: Tournament): boolean {
  return withinPast(t.first_seen_at, DAYS_NEW) || withinPast(t.registration_opens_at, DAYS_NEW)
}

// "ÖFFNET BALD" — registration hasn't opened yet but opens within DAYS_SOON days.
export function opensSoon(t: Tournament): boolean {
  if (!t.registration_opens_at) return false
  const diffMs = new Date(t.registration_opens_at).getTime() - Date.now()
  return diffMs > 0 && diffMs < DAYS_SOON * DAY_MS
}
