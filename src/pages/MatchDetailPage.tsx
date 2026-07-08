import { Helmet } from "react-helmet-async"
import { useState, useEffect, useCallback } from "react"
import { useParams, useSearchParams, Link } from "react-router-dom"
import {
  fetchMatch, fetchMatchPersonal, joinMatch, leaveMatch, patchMatch,
  addMatchPlayer, removeMatchPlayer, cancelMatch, MatchApiError,
} from "../api"
import type { MatchPublic, MatchPersonal } from "../types"
import {
  inputClass, labelClass, labelStyle, LevelPills,
  getStoredMatchToken, storeMatchToken, clearMatchToken, toViennaISO, viennaDateTimeParts,
  formatMatchWhen, formatPrice, courtTypeLabel, spotsLeftLabel, occupied, AvatarRow,
} from "./matchShared"
import { ShareMatchButton } from "./DeinMatchPage"

const JOIN_ERROR_MESSAGES: Record<string, string> = {
  "Zu langsam. Das Match ist voll.": "Zu langsam. Das Match ist voll.",
  "Du bist schon drin. Einmal reicht.": "Du bist schon drin. Einmal reicht.",
  invalid_name: "Dein Name fehlt oder ist zu lang.",
  invalid_phone: "Diese Nummer sieht falsch aus.",
}

type ViewState = "loading" | "notfound" | "ready"

export default function MatchDetailPage() {
  const { slug = "" } = useParams<{ slug: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlToken = searchParams.get("t")

  const [state, setState] = useState<ViewState>("loading")
  const [publicMatch, setPublicMatch] = useState<MatchPublic | null>(null)
  const [personal, setPersonal] = useState<MatchPersonal | null>(null)
  const [activeToken, setActiveToken] = useState<string | null>(null)

  const load = useCallback(async () => {
    setState("loading")
    const pub = await fetchMatch(slug).catch(() => null)
    if (!pub) { setState("notfound"); return }
    setPublicMatch(pub)

    const token = urlToken ?? getStoredMatchToken(slug)
    if (token) {
      const pers = await fetchMatchPersonal(slug, token)
      if (pers) {
        setPersonal(pers)
        setActiveToken(token)
        storeMatchToken(slug, token)
      } else {
        // Token no longer valid (e.g. removed by the organizer, or a mangled
        // URL) — drop it so we don't keep silently retrying it on every visit.
        setPersonal(null)
        setActiveToken(null)
        clearMatchToken(slug)
      }
    } else {
      setPersonal(null)
      setActiveToken(null)
    }
    setState("ready")
  }, [slug, urlToken])

  useEffect(() => { load() }, [load])

  // Changing searchParams updates `urlToken`, which changes `load`'s identity
  // and re-triggers the effect above with the correct (non-stale) token —
  // no need to call load() manually here.
  function onJoined(token: string) {
    storeMatchToken(slug, token)
    setSearchParams({ t: token }, { replace: true })
  }

  // Applies the API's own response directly instead of refetching: the just-used
  // player token is now dead, so a reload would race a stale urlToken/localStorage
  // token against the fresh state and throw a spurious 403 (fixed 2026-07-06).
  function onLeft(updatedMatch: MatchPublic) {
    setPublicMatch(updatedMatch)
    setPersonal(null)
    setActiveToken(null)
    clearMatchToken(slug)
    setSearchParams({}, { replace: true })
  }

  if (state === "loading") {
    return <div className="py-16 text-center text-gray-600 text-sm">Yara holt die Fakten …</div>
  }
  if (state === "notfound") {
    return (
      <div className="py-16 text-center">
        <p className="text-3xl mb-3">🎾</p>
        <p className="text-white font-semibold mb-1">Dieses Match existiert nicht.</p>
        <p className="text-gray-500 text-sm mb-4">Vielleicht hat es nie existiert.</p>
        <Link to="/dein-match" className="text-sm" style={{ color: "#d4f53c" }}>← Zu den offenen Matches</Link>
      </div>
    )
  }

  const match = publicMatch!
  const role = personal?.role

  return (
    <div>
      <Helmet>
        <title>{match.venue.name} · Dein Match — PadelYara</title>
        <meta name="robots" content="noindex, follow" />
      </Helmet>

      {activeToken && !personal && (
        <p className="text-xs mb-3" style={{ color: "#fbbf24" }}>Der Link ist ungültig. Ich kenne dich nicht.</p>
      )}

      <MatchHeader match={match} />

      {match.status === "cancelled" && (
        <StatusBanner text="Abgesagt. Von der Organisatorin, nicht von mir." />
      )}
      {match.status === "expired" && (
        <StatusBanner text="Das Match ist vorbei. Ob ihr gewonnen habt, weiß ich nicht — und es ist nicht mein Problem." />
      )}

      {match.status !== "cancelled" && match.status !== "expired" && (
        <>
          {role === "organizer" && personal && (
            <OrganizerPanel slug={slug} manageToken={activeToken!} personal={personal} onChanged={load} />
          )}
          {role === "player" && personal && (
            <PlayerPanel slug={slug} playerToken={activeToken!} personal={personal} onLeft={onLeft} />
          )}
          {!role && match.status === "open" && (
            <JoinForm slug={slug} onJoined={onJoined} />
          )}
          {!role && match.status === "full" && (
            <p className="text-sm text-gray-500 italic mt-4">Voll. Der Rest kommt zu spät.</p>
          )}
        </>
      )}
    </div>
  )
}

function StatusBanner({ text }: { text: string }) {
  return (
    <div className="rounded-xl p-4 mt-4 text-sm" style={{ background: "rgba(107,114,128,0.08)", border: "1px solid #374151", color: "#9ca3af" }}>
      {text}
    </div>
  )
}

function MatchHeader({ match }: { match: MatchPublic }) {
  const isFull = match.status === "full"
  return (
    <div className="rounded-xl p-4" style={{ background: "#111827", border: "1px solid #1f2937", opacity: isFull ? 0.75 : 1 }}>
      <div className="flex justify-between items-start gap-3 mb-1">
        <div>
          <Link to={`/court/${match.venue.id}`} className="font-semibold text-xl hover:underline" style={{ color: "#d4f53c" }}>
            {match.venue.name} →
          </Link>
          <p className="text-sm text-gray-200 mt-0.5">{formatMatchWhen(match.starts_at, match.ends_at)}</p>
          <p className="text-xs text-gray-600 mt-0.5">{courtTypeLabel(match.venue.court_type)}</p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {match.levels.map(l => (
            <span key={l} className="text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap" style={{ border: "1px solid rgba(212,245,60,0.4)", color: "#d4f53c" }}>{l}</span>
          ))}
          <span
            className="text-xs px-2 py-0.5 rounded-full whitespace-nowrap"
            style={match.court_booked
              ? { background: "rgba(74,222,128,0.1)", color: "#4ade80", border: "1px solid rgba(74,222,128,0.3)" }
              : { background: "rgba(251,191,36,0.09)", color: "#fbbf24", border: "1px solid rgba(251,191,36,0.3)" }}
          >
            {match.court_booked ? "✓ Court gebucht" : "Court noch nicht gebucht"}
          </span>
        </div>
      </div>

      <p className="text-sm text-gray-400 mt-2">Organisiert von <span className="text-white font-medium">{match.organizer.name}</span></p>
      <p className="text-sm mt-1" style={{ color: "#d4f53c" }}>{formatPrice(match.price_total, match.spots_total)}</p>
      {match.note && (
        <div className="mt-2 pl-2.5 py-1.5 text-sm text-gray-300 italic" style={{ borderLeft: "2px solid rgba(212,245,60,0.35)" }}>„{match.note}"</div>
      )}

      <p className="text-sm mt-3 mb-2" style={{ color: "#d4f53c" }}>
        {occupied(match)} von {match.spots_total} · <span style={{ color: match.status === "full" ? "#6b7280" : "rgba(212,245,60,0.45)" }}>{spotsLeftLabel(match)}</span>
      </p>
      <AvatarRow organizerName={match.organizer.name} players={match.players} spotsTotal={match.spots_total} />

      <div className="mt-3">
        <ShareMatchButton slug={match.slug} venueName={match.venue.name} />
      </div>
    </div>
  )
}

function JoinForm({ slug, onJoined }: { slug: string; onJoined: (token: string) => void }) {
  const [name, setName] = useState("")
  const [phone, setPhone] = useState("")
  const [email, setEmail] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reveal, setReveal] = useState<{ organizerPhone: string; token: string; match: MatchPublic } | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!name.trim()) { setError("Vorname reicht."); return }
    if (!phone.trim()) { setError("Deine Nummer fehlt."); return }
    setSubmitting(true)
    try {
      const res = await joinMatch(slug, { name: name.trim(), phone: phone.trim(), email: email.trim() || undefined })
      setReveal({ organizerPhone: res.organizer_phone, token: res.player_token, match: res.match })
    } catch (err) {
      const msg = err instanceof MatchApiError ? (JOIN_ERROR_MESSAGES[err.message] ?? err.message) : "Verbindung fehlgeschlagen."
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  if (reveal) {
    return (
      <div className="rounded-xl p-4 mt-4" style={{ background: "rgba(74,222,128,0.06)", border: "1px solid rgba(74,222,128,0.25)" }}>
        <p className="text-sm text-gray-400 mb-1">Organisator ist erreichbar unter:</p>
        <p className="text-lg font-bold tracking-wide" style={{ color: "#4ade80" }}>{reveal.organizerPhone}</p>
        <p className="text-xs text-gray-500 mt-1 mb-3">Nur für dich sichtbar. Nicht für andere Mitspieler.</p>
        <button
          onClick={() => onJoined(reveal.token)}
          className="w-full py-2.5 rounded-lg text-sm font-bold uppercase tracking-wide"
          style={{ background: "rgba(212,245,60,0.12)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.3)" }}
        >
          Alles klar
        </button>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl p-4 mt-4 flex flex-col gap-3" style={{ background: "#111318", border: "1px solid rgba(212,245,60,0.12)" }}>
      <p className="text-sm font-semibold text-white">Ich bin dabei</p>
      <div>
        <label className={`${labelClass} block mb-1.5`} style={labelStyle}>Dein Name</label>
        <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Vorname reicht" maxLength={40} className={inputClass} />
      </div>
      <div>
        <label className={`${labelClass} block mb-1.5`} style={labelStyle}>Handynummer</label>
        <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+43 …" className={inputClass} />
        <p className="text-xs text-gray-600 mt-1">Wird nur an die Organisatorin weitergegeben — nicht öffentlich sichtbar.</p>
      </div>
      <div>
        <label className={`${labelClass} block mb-1.5`} style={labelStyle}>E-Mail (optional — für Benachrichtigungen)</label>
        <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="deine@email.at" className={inputClass} />
      </div>
      {error && <p className="text-red-400 text-sm">{error}</p>}
      <button
        type="submit"
        disabled={submitting}
        className="w-full py-2.5 rounded-lg text-sm font-bold uppercase tracking-wide"
        style={{ background: "rgba(212,245,60,0.12)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.3)", opacity: submitting ? 0.6 : 1 }}
      >
        {submitting ? "…" : "Ich bin dabei → Bestätigen"}
      </button>
    </form>
  )
}

function PlayerPanel({ slug, playerToken, personal, onLeft }: {
  slug: string; playerToken: string; personal: MatchPersonal; onLeft: (match: MatchPublic) => void
}) {
  const [confirming, setConfirming] = useState(false)
  const [leaving, setLeaving] = useState(false)

  async function handleLeave() {
    setLeaving(true)
    try {
      const { match } = await leaveMatch(slug, playerToken)
      onLeft(match)
    } finally {
      setLeaving(false)
    }
  }

  return (
    <div className="rounded-xl p-4 mt-4" style={{ background: "rgba(74,222,128,0.06)", border: "1px solid rgba(74,222,128,0.25)" }}>
      <p className="text-sm text-gray-400 mb-1">Organisator ist erreichbar unter:</p>
      <p className="text-lg font-bold tracking-wide" style={{ color: "#4ade80" }}>{personal.organizer.phone}</p>
      <p className="text-xs text-gray-500 mt-1 mb-4">Nur für dich sichtbar. Nicht für andere Mitspieler.</p>

      {!confirming ? (
        <button onClick={() => setConfirming(true)} className="text-sm text-gray-500 underline">Doch nicht</button>
      ) : (
        <div className="flex items-center gap-3">
          <p className="text-sm text-gray-400">Wirklich austragen?</p>
          <button onClick={handleLeave} disabled={leaving} className="text-sm font-semibold" style={{ color: "#fb7185" }}>Ja, austragen</button>
          <button onClick={() => setConfirming(false)} className="text-sm text-gray-600">Abbrechen</button>
        </div>
      )}
    </div>
  )
}

function OrganizerPanel({ slug, manageToken, personal, onChanged }: {
  slug: string; manageToken: string; personal: MatchPersonal; onChanged: () => void
}) {
  const startParts = viennaDateTimeParts(personal.starts_at)
  const endParts = viennaDateTimeParts(personal.ends_at)

  const [date, setDate] = useState(startParts.date)
  const [startTime, setStartTime] = useState(startParts.time)
  const [endTime, setEndTime] = useState(endParts.time)
  const [courtBooked, setCourtBooked] = useState(personal.court_booked)
  const [priceTotal, setPriceTotal] = useState(personal.price_total != null ? String(personal.price_total) : "")
  const [levels, setLevels] = useState<string[]>(personal.levels)
  const [note, setNote] = useState(personal.note ?? "")
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [guestName, setGuestName] = useState("")
  const [guestPhone, setGuestPhone] = useState("")
  const [addingPlayer, setAddingPlayer] = useState(false)

  const [confirmingCancel, setConfirmingCancel] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaveError(null)
    setSaving(true)
    try {
      const priceNum = priceTotal.trim() === "" ? null : Number(priceTotal.replace(",", "."))
      await patchMatch(slug, manageToken, {
        starts_at: toViennaISO(date, startTime),
        ends_at: toViennaISO(date, endTime),
        levels,
        court_booked: courtBooked,
        price_total: priceNum,
        note: note.trim() || null,
      })
      onChanged()
    } catch {
      setSaveError("Konnte nicht gespeichert werden. Versuch's nochmal.")
    } finally {
      setSaving(false)
    }
  }

  async function handleAddPlayer() {
    const name = guestName.trim()
    if (!name) return
    setAddingPlayer(true)
    try {
      await addMatchPlayer(slug, manageToken, { name, phone: guestPhone.trim() || undefined })
      setGuestName("")
      setGuestPhone("")
      onChanged()
    } finally {
      setAddingPlayer(false)
    }
  }

  async function handleRemovePlayer(token: string) {
    await removeMatchPlayer(slug, manageToken, token)
    onChanged()
  }

  async function handleCancel() {
    setCancelling(true)
    try {
      await cancelMatch(slug, manageToken)
      onChanged()
    } finally {
      setCancelling(false)
    }
  }

  return (
    <div className="rounded-xl p-4 mt-4" style={{ background: "#111318", border: "1px solid rgba(212,245,60,0.12)" }}>
      <p className="text-sm font-semibold text-white mb-3">Match verwalten</p>

      <div className="mb-4">
        <p className={`${labelClass} block mb-2`} style={labelStyle}>Mitspieler</p>
        <div className="flex flex-col gap-2">
          {personal.players.map(p => (
            <div key={p.token} className="flex items-center justify-between text-sm bg-gray-900/50 rounded-lg px-3 py-2">
              <span className="text-white">{p.name}{p.phone ? <span className="text-gray-500"> · {p.phone}</span> : null}</span>
              <button onClick={() => p.token && handleRemovePlayer(p.token)} className="text-xs" style={{ color: "#fb7185" }}>entfernen</button>
            </div>
          ))}
          {personal.players.length === 0 && <p className="text-xs text-gray-600">Noch niemand dabei.</p>}
        </div>
        {personal.players.length < 3 && (
          <div className="flex gap-2 mt-2">
            <input type="text" value={guestName} onChange={e => setGuestName(e.target.value)} placeholder="Name" maxLength={40} className={`${inputClass} flex-1 py-2`} />
            <input type="tel" value={guestPhone} onChange={e => setGuestPhone(e.target.value)} placeholder="Nummer (optional)" className={`${inputClass} flex-1 py-2`} />
            <button type="button" onClick={handleAddPlayer} disabled={addingPlayer} className="px-3 rounded-lg text-xs border border-dashed border-gray-700 text-gray-500 shrink-0">+ hinzufügen</button>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="flex flex-col gap-3 pt-3" style={{ borderTop: "1px solid #1f2937" }}>
        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className={`${labelClass} block mb-1.5`} style={labelStyle}>Datum</label>
            <input type="date" value={date} onChange={e => setDate(e.target.value)} className={`${inputClass} py-2`} />
          </div>
          <div>
            <label className={`${labelClass} block mb-1.5`} style={labelStyle}>Von</label>
            <input type="time" value={startTime} onChange={e => setStartTime(e.target.value)} className={`${inputClass} py-2`} />
          </div>
          <div>
            <label className={`${labelClass} block mb-1.5`} style={labelStyle}>Bis</label>
            <input type="time" value={endTime} onChange={e => setEndTime(e.target.value)} className={`${inputClass} py-2`} />
          </div>
        </div>

        <div className="flex gap-2 items-center">
          <label className={labelClass} style={labelStyle}>Court gebucht</label>
          <button type="button" onClick={() => setCourtBooked(!courtBooked)} className="text-xs px-2.5 py-1 rounded-full border" style={{ borderColor: courtBooked ? "#4ade80" : "rgba(107,114,128,0.4)", color: courtBooked ? "#4ade80" : "#9ca3af" }}>
            {courtBooked ? "Ja" : "Nein"}
          </button>
        </div>

        <div>
          <label className={`${labelClass} block mb-1.5`} style={labelStyle}>Preis gesamt (€)</label>
          <input type="number" min={0} max={200} step={0.5} value={priceTotal} onChange={e => setPriceTotal(e.target.value)} className={`${inputClass} py-2`} />
        </div>

        <div>
          <label className={`${labelClass} block mb-1.5`} style={labelStyle}>Level</label>
          <LevelPills selected={levels} onChange={setLevels} />
        </div>

        <div>
          <label className={`${labelClass} block mb-1.5`} style={labelStyle}>Notiz</label>
          <input type="text" value={note} onChange={e => setNote(e.target.value)} maxLength={200} className={`${inputClass} py-2`} />
        </div>

        {saveError && <p className="text-red-400 text-sm">{saveError}</p>}

        <button type="submit" disabled={saving} className="w-full py-2.5 rounded-lg text-sm font-bold uppercase tracking-wide" style={{ background: "rgba(212,245,60,0.12)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.3)" }}>
          {saving ? "…" : "Speichern"}
        </button>
      </form>

      <div className="mt-4 pt-3" style={{ borderTop: "1px solid #1f2937" }}>
        {!confirmingCancel ? (
          <button onClick={() => setConfirmingCancel(true)} className="text-sm" style={{ color: "#fb7185" }}>Match absagen</button>
        ) : (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-gray-400">Sicher? Ich sage allen Bescheid. Peinlich wird es trotzdem.</p>
            <div className="flex gap-3">
              <button onClick={handleCancel} disabled={cancelling} className="text-sm font-semibold" style={{ color: "#fb7185" }}>Ja, absagen</button>
              <button onClick={() => setConfirmingCancel(false)} className="text-sm text-gray-600">Doch nicht</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
