export function formatDate(isoStr: string | null, includeYear = true): string {
  if (!isoStr) return ""
  const d = new Date(isoStr)
  return d.toLocaleDateString("de-AT", {
    weekday: "short", day: "2-digit", month: "2-digit",
    ...(includeYear ? { year: "numeric" } : {}),
  })
}

export function formatTime(isoStr: string | null): string {
  if (!isoStr) return ""
  const d = new Date(isoStr)
  return d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" })
}

function isSameDay(a: string, b: string): boolean {
  return a.slice(0, 10) === b.slice(0, 10)
}

export function formatDateRange(starts: string | null, ends: string | null): string {
  if (!starts) return ""
  if (!ends || ends === starts) {
    return `${formatDate(starts)}, ${formatTime(starts)} Uhr`
  }
  if (isSameDay(starts, ends)) {
    return `${formatDate(starts)}, ${formatTime(starts)} – ${formatTime(ends)} Uhr`
  }
  return `${formatDate(starts, false)} – ${formatDate(ends)}`
}
