import { useState } from "react"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"

export interface JagdAlarmModalProps {
  isOpen: boolean
  onClose: () => void
  filters: {
    bundeslaender: string[]
    categories: string[]
    competitions: string[]
    weekdays: string[]
    venueNames: string[]
  }
}

function FilterSummary({ filters }: { filters: JagdAlarmModalProps["filters"] }) {
  const lines: { label: string; values: string[] }[] = [
    { label: "Bundesland", values: filters.bundeslaender },
    { label: "Level", values: filters.categories },
    { label: "Wettbewerb", values: filters.competitions },
    { label: "Wochentag", values: filters.weekdays },
    { label: "Standort", values: filters.venueNames },
  ].filter(l => l.values.length > 0)

  if (lines.length === 0) {
    return (
      <p className="text-xs" style={{ color: "#6b7280" }}>
        Alle Turniere — keine Filter aktiv.
      </p>
    )
  }

  return (
    <div className="space-y-1">
      {lines.map(l => (
        <div key={l.label} className="flex gap-2 text-xs">
          <span style={{ color: "#6b7280", minWidth: "6rem" }}>{l.label}</span>
          <span style={{ color: "#d1d5db" }}>{l.values.join(", ")}</span>
        </div>
      ))}
    </div>
  )
}

export default function JagdAlarmModal({ isOpen, onClose, filters }: JagdAlarmModalProps) {
  const [email, setEmail] = useState("")
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle")
  const [errorMsg, setErrorMsg] = useState("")

  if (!isOpen) return null

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setStatus("loading")
    setErrorMsg("")

    try {
      const res = await fetch(`${API_BASE}/api/tournaments/alerts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          filters: {
            bundesland: filters.bundeslaender,
            category: filters.categories,
            competition: filters.competitions,
            weekday: filters.weekdays,
            venue_name: filters.venueNames,
          },
        }),
      })
      const data = await res.json()
      if (!res.ok || !data.ok) {
        setErrorMsg(data.error === "invalid_email" ? "Ungültige E-Mail-Adresse." : "Etwas ist schiefgelaufen.")
        setStatus("error")
        return
      }
      setStatus("success")
    } catch {
      setErrorMsg("Verbindung fehlgeschlagen. Bitte nochmal versuchen.")
      setStatus("error")
    }
  }

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.75)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      {/* Modal */}
      <div
        className="w-full max-w-md rounded-2xl border p-6 relative"
        style={{ background: "#080810", borderColor: "rgba(212,245,60,0.15)" }}
      >
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-600 hover:text-gray-400 transition-colors text-lg leading-none"
          aria-label="Schließen"
        >
          ✕
        </button>

        {status === "success" ? (
          // Success state
          <div className="text-center py-4">
            <p
              className="text-xl font-bold mb-2"
              style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c", letterSpacing: "0.04em" }}
            >
              CHECK DEIN POSTFACH.
            </p>
            <p className="text-sm" style={{ color: "#6b7280" }}>
              Bestätigungslink unterwegs. Sobald du klickst, bist du dabei.
            </p>
          </div>
        ) : (
          <>
            {/* Header */}
            <p
              className="text-lg font-bold mb-1"
              style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c", letterSpacing: "0.05em" }}
            >
              JAGD-ALARM
            </p>
            <p className="text-sm mb-5" style={{ color: "#6b7280" }}>
              Yara schreibt dir, wenn neue Turniere auftauchen.
            </p>

            {/* Filter summary */}
            <div
              className="rounded-lg border p-3 mb-5"
              style={{ borderColor: "rgba(107,114,128,0.2)", background: "rgba(255,255,255,0.02)" }}
            >
              <p
                className="text-xs mb-2 tracking-widest uppercase"
                style={{ color: "#6b7280", fontFamily: "'Barlow Condensed', sans-serif" }}
              >
                Deine Filter
              </p>
              <FilterSummary filters={filters} />
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-3">
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="deine@email.at"
                required
                className="w-full rounded-lg border px-4 py-3 text-sm outline-none transition-colors"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  borderColor: "rgba(107,114,128,0.3)",
                  color: "#d1d5db",
                }}
                onFocus={e => { e.currentTarget.style.borderColor = "#d4f53c" }}
                onBlur={e => { e.currentTarget.style.borderColor = "rgba(107,114,128,0.3)" }}
              />

              {status === "error" && (
                <p className="text-xs" style={{ color: "#f87171" }}>{errorMsg}</p>
              )}

              <button
                type="submit"
                disabled={status === "loading"}
                className="w-full rounded-lg py-3 text-sm font-bold tracking-widest uppercase transition-opacity"
                style={{
                  fontFamily: "'Barlow Condensed', sans-serif",
                  background: "#d4f53c",
                  color: "#000000",
                  opacity: status === "loading" ? 0.6 : 1,
                  cursor: status === "loading" ? "not-allowed" : "pointer",
                }}
              >
                {status === "loading" ? "…" : "Jagd-Alarm aktivieren"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
