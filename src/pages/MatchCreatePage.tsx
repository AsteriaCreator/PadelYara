import { Helmet } from "react-helmet-async"
import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { createMatch, fetchVenues, MatchApiError } from "../api"
import type { MapVenue } from "../types"
import {
  inputClass, labelClass, labelStyle, LEVEL_SNARK,
  storeMatchToken, toViennaISO,
} from "./matchShared"
import { LevelPills } from "./matchComponents"

function getNowVienna() {
  const now = new Date()
  const viennaStr = now.toLocaleString("sv-SE", { timeZone: "Europe/Vienna" })
  const [datePart, timePart] = viennaStr.split(" ")
  return { datePart, hour: Number(timePart.split(":")[0]) }
}

function defaultTimes(): { date: string; start: string; end: string } {
  const v = getNowVienna()
  const startHour = Math.min(22, v.hour + 1)
  const pad = (n: number) => String(n).padStart(2, "0")
  return { date: v.datePart, start: `${pad(startHour)}:00`, end: `${pad(Math.min(23, startHour + 1))}:30` }
}

const ERROR_MESSAGES: Record<string, string> = {
  invalid_time: "Zeit stimmt nicht. Bitte nochmal prüfen.",
  end_before_start: "Ende muss nach dem Start liegen.",
  starts_in_past: "Diese Zeit ist vorbei. Wähl eine, die noch kommt.",
  duration_too_long: "Vier Stunden reichen. Wirklich.",
  invalid_levels: "Wähl mindestens ein Level.",
  invalid_price: "Preis muss zwischen 0 und 200 € liegen.",
  invalid_organizer_name: "Dein Name fehlt oder ist zu lang.",
  invalid_phone: "Diese Nummer sieht falsch aus.",
  invalid_email: "Diese E-Mail sieht falsch aus.",
  invalid_guest_name: "Der Name deines Mitspielers fehlt oder ist zu lang.",
  too_many_guests: "Mehr als drei Mitspieler passen nicht rein.",
  unknown_venue: "Diese Venue kennt Yara nicht.",
}

export default function MatchCreatePage() {
  const navigate = useNavigate()
  const { date: defaultDate, start: defaultStart, end: defaultEnd } = defaultTimes()

  const [allVenues, setAllVenues] = useState<MapVenue[]>([])
  const [venueQuery, setVenueQuery] = useState("")
  const [venue, setVenue] = useState<MapVenue | null>(null)
  const [showVenueDropdown, setShowVenueDropdown] = useState(false)
  const venueWrapperRef = useRef<HTMLDivElement>(null)

  const [date, setDate] = useState(defaultDate)
  const [startTime, setStartTime] = useState(defaultStart)
  const [endTime, setEndTime] = useState(defaultEnd)
  const [courtBooked, setCourtBooked] = useState(true)
  const [priceTotal, setPriceTotal] = useState("")
  const [organizerName, setOrganizerName] = useState("")
  const [organizerPhone, setOrganizerPhone] = useState("")
  const [organizerEmail, setOrganizerEmail] = useState("")
  const [levels, setLevels] = useState<string[]>([])
  const [guestName, setGuestName] = useState("")
  const [guestPhone, setGuestPhone] = useState("")
  const [guests, setGuests] = useState<{ name: string; phone?: string }[]>([])
  const [note, setNote] = useState("")

  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [result, setResult] = useState<{ slug: string; manageToken: string } | null>(null)

  useEffect(() => { fetchVenues().then(setAllVenues).catch(() => {}) }, [])

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (venueWrapperRef.current && !venueWrapperRef.current.contains(e.target as Node)) setShowVenueDropdown(false)
    }
    document.addEventListener("pointerdown", onPointerDown)
    return () => document.removeEventListener("pointerdown", onPointerDown)
  }, [])

  const venueMatches = venueQuery.trim().length >= 1
    ? allVenues.filter(v => v.name.toLowerCase().includes(venueQuery.trim().toLowerCase())).slice(0, 8)
    : []

  const priceNum = priceTotal.trim() === "" ? null : Number(priceTotal.replace(",", "."))
  const perPerson = priceNum != null && !isNaN(priceNum) ? (priceNum / 4).toFixed(2).replace(".", ",") : null

  function addGuest() {
    const name = guestName.trim()
    if (!name) return
    if (guests.length >= 3) return
    setGuests([...guests, { name, phone: guestPhone.trim() || undefined }])
    setGuestName("")
    setGuestPhone("")
  }
  function removeGuest(i: number) {
    setGuests(guests.filter((_, idx) => idx !== i))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)

    if (!venue) { setFormError("Wähl eine Venue."); return }
    if (levels.length === 0) { setFormError("Wähl mindestens ein Level."); return }
    if (!organizerName.trim()) { setFormError("Dein Name fehlt."); return }
    if (!organizerPhone.trim()) { setFormError("Deine Nummer fehlt."); return }
    if (!organizerEmail.trim()) { setFormError("Deine E-Mail fehlt — sonst erfährst du nichts."); return }

    setSubmitting(true)
    try {
      const { slug, manage_token } = await createMatch({
        venue_id: venue.id,
        starts_at: toViennaISO(date, startTime),
        ends_at: toViennaISO(date, endTime),
        levels,
        court_booked: courtBooked,
        price_total: priceNum,
        note: note.trim() || null,
        organizer_name: organizerName.trim(),
        organizer_phone: organizerPhone.trim(),
        organizer_email: organizerEmail.trim(),
        guest_players: guests,
      })
      storeMatchToken(slug, manage_token)
      setResult({ slug, manageToken: manage_token })
    } catch (err) {
      const msg = err instanceof MatchApiError ? (ERROR_MESSAGES[err.message] ?? err.message) : "Verbindung fehlgeschlagen."
      setFormError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  if (result) {
    return <CreateSuccess slug={result.slug} manageToken={result.manageToken} onDone={() => navigate(`/match/${result.slug}`)} />
  }

  return (
    <div>
      <Helmet>
        <title>Match aufmachen — PadelYara</title>
        <meta name="robots" content="noindex, follow" />
      </Helmet>

      <p className="text-base italic mb-5 mt-2" style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c" }}>
        Vier müsst ihr sein. Den Anfang mache ich.
      </p>

      <form onSubmit={handleSubmit} className="rounded-xl p-4 flex flex-col gap-4" style={{ background: "#111318", border: "1px solid rgba(212,245,60,0.12)" }}>
        <div className="relative" ref={venueWrapperRef}>
          <label className={`${labelClass} block mb-2`} style={labelStyle}>Venue</label>
          <input
            type="text"
            value={venue ? venue.name : venueQuery}
            onChange={e => { setVenue(null); setVenueQuery(e.target.value); setShowVenueDropdown(true) }}
            onFocus={() => setShowVenueDropdown(true)}
            placeholder="Venue suchen …"
            className={inputClass}
          />
          {showVenueDropdown && venueMatches.length > 0 && (
            <ul className="absolute z-30 left-0 right-0 top-full mt-1 bg-gray-800 border border-gray-700 rounded-lg overflow-hidden shadow-lg max-h-52 overflow-y-auto">
              {venueMatches.map(v => (
                <li
                  key={v.id}
                  onPointerDown={e => { e.preventDefault(); setVenue(v); setVenueQuery(""); setShowVenueDropdown(false) }}
                  className="px-3 py-2 text-sm text-white cursor-pointer hover:bg-gray-700 truncate"
                >
                  {v.name}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={`${labelClass} block mb-2`} style={labelStyle}>Datum</label>
            <input type="date" value={date} onChange={e => setDate(e.target.value)} className={inputClass} />
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className={`${labelClass} block mb-2`} style={labelStyle}>Von</label>
              <input type="time" value={startTime} onChange={e => setStartTime(e.target.value)} className={inputClass} />
            </div>
            <div className="flex-1">
              <label className={`${labelClass} block mb-2`} style={labelStyle}>Bis</label>
              <input type="time" value={endTime} onChange={e => setEndTime(e.target.value)} className={inputClass} />
            </div>
          </div>
        </div>

        <div>
          <label className={`${labelClass} block mb-2`} style={labelStyle}>Court schon gebucht?</label>
          <div className="flex gap-2">
            {([true, false] as const).map(v => (
              <button
                key={String(v)}
                type="button"
                onClick={() => setCourtBooked(v)}
                className="flex-1 py-2 rounded-lg text-sm font-semibold border transition-colors"
                style={{
                  borderColor: courtBooked === v ? "#d4f53c" : "rgba(107,114,128,0.4)",
                  color: courtBooked === v ? "#d4f53c" : "#9ca3af",
                  background: courtBooked === v ? "rgba(212,245,60,0.1)" : "transparent",
                }}
              >
                {v ? "Ja" : "Nein — noch offen"}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={`${labelClass} block mb-2`} style={labelStyle}>Preis gesamt (€)</label>
            <input type="number" min={0} max={200} step={0.5} value={priceTotal} onChange={e => setPriceTotal(e.target.value)} placeholder="optional" className={inputClass} />
          </div>
          <div>
            <label className={`${labelClass} block mb-2`} style={labelStyle}>Pro Person</label>
            <input type="text" readOnly value={perPerson ? `${perPerson} € (÷ 4)` : "—"} className={`${inputClass} opacity-60`} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={`${labelClass} block mb-2`} style={labelStyle}>Dein Name</label>
            <input type="text" value={organizerName} onChange={e => setOrganizerName(e.target.value)} maxLength={40} className={inputClass} />
          </div>
          <div>
            <label className={`${labelClass} block mb-2`} style={labelStyle}>Deine Handynummer</label>
            <input type="tel" value={organizerPhone} onChange={e => setOrganizerPhone(e.target.value)} placeholder="+43 …" className={inputClass} />
          </div>
        </div>

        <div>
          <label className={`${labelClass} block mb-2`} style={labelStyle}>E-Mail (für Benachrichtigungen)</label>
          <input type="email" value={organizerEmail} onChange={e => setOrganizerEmail(e.target.value)} placeholder="deine@email.at" className={inputClass} />
          <p className="text-xs text-gray-600 mt-1">Du bekommst eine Mail wenn jemand beitritt oder absagt.</p>
        </div>

        <div>
          <label className={`${labelClass} block mb-2`} style={labelStyle}>Level (mehrere möglich)</label>
          <LevelPills selected={levels} onChange={setLevels} />
          <p className="text-xs mt-2 italic" style={{ color: "rgba(212,245,60,0.5)" }}>{LEVEL_SNARK}</p>
        </div>

        <div>
          <label className={`${labelClass} block mb-2`} style={labelStyle}>Mitspieler eintragen (optional)</label>
          {guests.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {guests.map((g, i) => (
                <span key={i} className="text-xs px-2.5 py-1 rounded-full flex items-center gap-1.5" style={{ background: "rgba(212,245,60,0.1)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.3)" }}>
                  {g.name}
                  <button type="button" onClick={() => removeGuest(i)} aria-label={`${g.name} entfernen`}>✕</button>
                </span>
              ))}
            </div>
          )}
          {guests.length < 3 && (
            <div className="flex gap-2">
              <input type="text" value={guestName} onChange={e => setGuestName(e.target.value)} placeholder="Name" maxLength={40} className={`${inputClass} flex-1`} />
              <input type="tel" value={guestPhone} onChange={e => setGuestPhone(e.target.value)} placeholder="Nummer (optional)" className={`${inputClass} flex-1`} />
              <button type="button" onClick={addGuest} className="px-3 rounded-lg text-sm border border-dashed border-gray-700 text-gray-500 shrink-0">+ hinzufügen</button>
            </div>
          )}
        </div>

        <div>
          <label className={`${labelClass} block mb-2`} style={labelStyle}>Notiz (optional)</label>
          <input type="text" value={note} onChange={e => setNote(e.target.value)} maxLength={200} placeholder="z. B. Bälle mitbringen, wir spielen locker" className={inputClass} />
        </div>

        {formError && <p className="text-red-400 text-sm">{formError}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-3 rounded-xl text-sm font-bold tracking-wide uppercase transition-colors"
          style={{ background: "rgba(212,245,60,0.12)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.3)", opacity: submitting ? 0.6 : 1 }}
        >
          {submitting ? "…" : "Match aufmachen → Link teilen"}
        </button>
      </form>
    </div>
  )
}

function CreateSuccess({ slug, manageToken, onDone }: { slug: string; manageToken: string; onDone: () => void }) {
  const [copiedPublic, setCopiedPublic] = useState(false)
  const [copiedManage, setCopiedManage] = useState(false)
  const publicUrl = `${window.location.origin}/match/${slug}`
  const manageUrl = `${window.location.origin}/match/${slug}?t=${manageToken}`
  const whatsappText = encodeURIComponent(`Wer spielt mit? ${publicUrl}\nLink in die Gruppe. Wer ihn ignoriert, spielt nicht.`)

  function copy(url: string, setCopied: (v: boolean) => void) {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="rounded-xl p-5" style={{ background: "#111318", border: "1px solid rgba(212,245,60,0.2)" }}>
      <p className="text-lg font-semibold text-white mb-1">Dein Match steht.</p>
      <p className="text-sm text-gray-400 mb-5">Link in die Gruppe. Wer ihn ignoriert, spielt nicht.</p>

      <p className={`${labelClass} block mb-2`} style={labelStyle}>Öffentlicher Link (zum Teilen)</p>
      <div className="flex gap-2 mb-2">
        <input readOnly value={publicUrl} className={`${inputClass} text-sm`} />
        <button onClick={() => copy(publicUrl, setCopiedPublic)} className="px-3 rounded-lg text-xs font-bold uppercase shrink-0" style={{ background: "rgba(212,245,60,0.12)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.3)" }}>
          {copiedPublic ? "Kopiert" : "Kopieren"}
        </button>
      </div>
      <a
        href={`https://wa.me/?text=${whatsappText}`}
        target="_blank"
        rel="noopener noreferrer"
        className="block w-full text-center py-2.5 rounded-lg text-sm font-bold mb-6"
        style={{ background: "#25D366", color: "#052e14" }}
      >
        In WhatsApp teilen
      </a>

      <div className="p-3 rounded-lg mb-4" style={{ background: "rgba(212,245,60,0.05)", border: "1px solid rgba(212,245,60,0.2)" }}>
        <p className={`${labelClass} block mb-1`} style={labelStyle}>Dein Schlüssel — der Manage-Link</p>
        <p className="text-xs text-gray-500 mb-2">Verlier ihn nicht. Ich schick ihn dir zur Sicherheit auch per Mail.</p>
        <div className="flex gap-2">
          <input readOnly value={manageUrl} className={`${inputClass} text-sm`} />
          <button onClick={() => copy(manageUrl, setCopiedManage)} className="px-3 rounded-lg text-xs font-bold uppercase shrink-0" style={{ background: "rgba(212,245,60,0.12)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.3)" }}>
            {copiedManage ? "Kopiert" : "Kopieren"}
          </button>
        </div>
      </div>

      <button onClick={onDone} className="w-full py-2.5 rounded-lg text-sm text-gray-400 border border-gray-700">
        Zum Match
      </button>
    </div>
  )
}
