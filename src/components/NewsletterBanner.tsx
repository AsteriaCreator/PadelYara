import React, { useState, useCallback, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { subscribeEmail } from "../api"

export default function NewsletterBanner() {
  const [searchParams, setSearchParams] = useSearchParams()
  const confirmedParam = searchParams.get("confirmed") === "1"
  const [email, setEmail] = useState("")
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error" | "confirmed">(
    confirmedParam ? "confirmed" : "idle"
  )
  const [alreadySubscribed, setAlreadySubscribed] = useState(false)

  useEffect(() => {
    if (confirmedParam) {
      const p = new URLSearchParams(searchParams)
      p.delete("confirmed")
      setSearchParams(p, { replace: true })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || status === "loading") return
    setStatus("loading")
    try {
      const res = await subscribeEmail(email.trim())
      if (res.ok) {
        setAlreadySubscribed(res.already ?? false)
        setStatus("done")
      } else {
        setStatus("error")
      }
    } catch {
      setStatus("error")
    }
  }, [email, status])

  if (status === "confirmed") {
    return (
      <div className="mb-4 px-4 py-3 rounded-xl text-sm" style={{ background: "rgba(212,245,60,0.06)", border: "1px solid rgba(212,245,60,0.2)" }}>
        <p style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c", fontSize: "1rem" }}>
          Bestätigt. Du bekommst Bescheid.
        </p>
      </div>
    )
  }

  if (status === "done") {
    return (
      <div className="mb-4 px-4 py-3 rounded-xl text-sm" style={{ background: "rgba(212,245,60,0.06)", border: "1px solid rgba(212,245,60,0.2)" }}>
        <p style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c", fontSize: "1rem" }}>
          {alreadySubscribed ? "Ich weiß. Du bist schon auf der Liste." : "Check deine Mails."}
        </p>
      </div>
    )
  }

  return (
    <div className="mb-4 px-4 py-3 rounded-xl" style={{ background: "rgba(212,245,60,0.04)", border: "1px solid rgba(212,245,60,0.12)" }}>
      <p className="text-sm mb-2" style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "rgba(212,245,60,0.7)", fontSize: "0.95rem" }}>
        Neue Features kommen. Ob du das mitbekommst, ist deine Entscheidung.
      </p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <label htmlFor="newsletter-email" className="sr-only">E-Mail-Adresse</label>
        <input
          id="newsletter-email"
          type="email"
          placeholder="deine@email.at"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className="flex-1 bg-transparent rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 outline-none min-w-0"
          style={{ border: "1px solid rgba(212,245,60,0.2)", fontFamily: "'Barlow Condensed', sans-serif" }}
        />
        <button
          type="submit"
          disabled={status === "loading"}
          className="px-4 py-1.5 rounded-lg text-sm font-bold tracking-wide transition-colors"
          style={{ fontFamily: "'Barlow Condensed', sans-serif", background: "rgba(212,245,60,0.12)", color: "#d4f53c", border: "1px solid rgba(212,245,60,0.3)" }}
        >
          {status === "loading" ? "…" : "INFORMIER MICH"}
        </button>
      </form>
      {status === "error" && (
        <p className="text-red-400 text-xs mt-1">Etwas ist schiefgelaufen. Versuch es nochmal.</p>
      )}
      <p className="text-xs mt-2" style={{ color: "rgba(156,163,175,0.7)" }}>
        Mit der Anmeldung stimmst du der Verarbeitung deiner E-Mail gemäß unserer{" "}
        <a href="/datenschutz" className="underline hover:opacity-80">Datenschutzerklärung</a> zu.
      </p>
    </div>
  )
}
