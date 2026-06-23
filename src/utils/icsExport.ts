import type { Tournament } from "../types"

function icsDate(iso: string | null, allDay: boolean): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ""
  if (allDay) {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, "0")
    const day = String(d.getDate()).padStart(2, "0")
    return `${y}${m}${day}`
  }
  return d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "")
}

function icsEscape(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n")
}

export function exportRegistrationReminder(t: Tournament): void {
  if (!t.registration_opens_at) return

  const start = icsDate(t.registration_opens_at, false)
  if (!start) return

  // 30-minute reminder block
  const endDt = new Date(t.registration_opens_at)
  endDt.setMinutes(endDt.getMinutes() + 30)
  const end = icsDate(endDt.toISOString(), false)

  const uid = `registration-${t.source_id}@padelyara.at`
  const now = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "")

  const descParts = [
    `Anmeldung für: ${t.title}`,
    t.source_url && `Link: ${t.source_url}`,
  ].filter(Boolean)
  const description = descParts.join("\\n")

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//PadelYara//Turnierjäger//DE",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${uid}`,
    `DTSTAMP:${now}`,
    `DTSTART:${start}`,
    `DTEND:${end}`,
    `SUMMARY:${icsEscape(`Anmeldung öffnet: ${t.title}`)}`,
    `DESCRIPTION:${description}`,
    t.source_url && `URL:${t.source_url}`,
    "BEGIN:VALARM",
    "TRIGGER:-PT0M",
    "ACTION:DISPLAY",
    `DESCRIPTION:${icsEscape(`Anmeldung öffnet jetzt: ${t.title}`)}`,
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
  ].filter(Boolean).join("\r\n")

  const blob = new Blob([lines], { type: "text/calendar;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `Anmeldung – ${t.title.replace(/[^a-zA-Z0-9äöüÄÖÜß\s-]/g, "").trim()}.ics`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function exportToCalendar(t: Tournament): void {
  const hasTime = t.starts_at?.includes("T") && !t.starts_at.endsWith("T00:00:00")
  const allDay = !hasTime

  const start = icsDate(t.starts_at, allDay)
  // ends_at for all-day events in ICS is exclusive — add one day past the last day
  let end = ""
  if (allDay) {
    const base = t.ends_at ?? t.starts_at
    const d = base ? new Date(base) : null
    if (d && !isNaN(d.getTime())) {
      d.setDate(d.getDate() + 1)
      end = icsDate(d.toISOString(), true)
    }
  } else {
    end = t.ends_at ? icsDate(t.ends_at, false) : start
  }

  if (!start) return

  const uid = `tournament-${t.source_id}@padelyara.at`
  const now = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "")

  const location = [t.venue_name, t.bundesland].filter(Boolean).join(", ")
  const descParts = [
    t.category && `Level: ${t.category}`,
    t.competition && `Wettbewerb: ${t.competition}`,
    t.source_url && `Details: ${t.source_url}`,
  ].filter(Boolean)
  const description = descParts.join("\\n")

  const dtStartProp = allDay ? `DTSTART;VALUE=DATE:${start}` : `DTSTART:${start}`
  const dtEndProp = end ? (allDay ? `DTEND;VALUE=DATE:${end}` : `DTEND:${end}`) : ""

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//PadelYara//Turnierjäger//DE",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${uid}`,
    `DTSTAMP:${now}`,
    dtStartProp,
    dtEndProp,
    `SUMMARY:${icsEscape(t.title)}`,
    location && `LOCATION:${icsEscape(location)}`,
    description && `DESCRIPTION:${description}`,
    t.source_url && `URL:${t.source_url}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ].filter(Boolean).join("\r\n")

  const blob = new Blob([lines], { type: "text/calendar;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `${t.title.replace(/[^a-zA-Z0-9äöüÄÖÜß\s-]/g, "").trim()}.ics`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
