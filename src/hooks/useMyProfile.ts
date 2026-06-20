import { useState, useEffect } from "react"
import type { Tournament } from "../types"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"
export const MY_SLUG_KEY = "turnierjager_player_slug"

export function useMyProfile() {
  const [mySlug, setMySlug] = useState<string>(() => localStorage.getItem(MY_SLUG_KEY) ?? "")
  const [myName, setMyName] = useState<string>(() => localStorage.getItem(MY_SLUG_KEY + "_name") ?? "")
  const [myInput, setMyInput] = useState("")
  const [mySuggestions, setMySuggestions] = useState<{ name: string; slug: string }[]>([])
  const [myTournaments, setMyTournaments] = useState<Tournament[]>([])
  const [myLoading, setMyLoading] = useState(false)
  const [myError, setMyError] = useState<string | null>(null)

  async function fetchMyTournaments(slug: string) {
    if (!slug) return
    setMyLoading(true)
    setMyError(null)
    try {
      const res = await fetch(`${API_BASE}/api/tournaments/player?slug=${encodeURIComponent(slug)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setMyTournaments(data.tournaments ?? [])
    } catch {
      setMyError("Abfrage fehlgeschlagen. Bitte nochmal versuchen.")
    } finally {
      setMyLoading(false)
    }
  }

  async function searchMyName(q: string) {
    setMyInput(q)
    if (q.length < 2) { setMySuggestions([]); return }
    try {
      const res = await fetch(`${API_BASE}/api/tournaments/players/search?q=${encodeURIComponent(q)}`)
      const data = await res.json()
      setMySuggestions(data.players ?? [])
    } catch {
      setMySuggestions([])
    }
  }

  function selectPlayer(name: string, slug: string) {
    setMySlug(slug)
    setMyName(name)
    setMyInput("")
    setMySuggestions([])
    localStorage.setItem(MY_SLUG_KEY, slug)
    localStorage.setItem(MY_SLUG_KEY + "_name", name)
    void fetchMyTournaments(slug)
  }

  function clearMyProfile() {
    setMySlug("")
    setMyName("")
    setMyInput("")
    setMySuggestions([])
    setMyTournaments([])
    localStorage.removeItem(MY_SLUG_KEY)
    localStorage.removeItem(MY_SLUG_KEY + "_name")
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (mySlug) void fetchMyTournaments(mySlug)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return {
    mySlug, myName, myInput, mySuggestions, myTournaments, myLoading, myError,
    searchMyName, selectPlayer, clearMyProfile,
  }
}
