import { useState, useEffect } from "react"
import type { Tournament } from "../types"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"
export const MY_SLUG_KEY = "turnierjager_player_slug"

export interface HistoryEntry {
  title: string
  date: string
  category: string
  competition: string
  url: string | null
  points: number
}

export interface MatchResult {
  wins: number
  losses: number
  partner: string | null
  partner_slug: string | null
  title: string
  date: string
}

export function useMyProfile(opts?: { skipInitialLoad?: boolean }) {
  const [mySlug, setMySlug] = useState<string>(() => opts?.skipInitialLoad ? "" : (localStorage.getItem(MY_SLUG_KEY) ?? ""))
  const [myName, setMyName] = useState<string>(() => opts?.skipInitialLoad ? "" : (localStorage.getItem(MY_SLUG_KEY + "_name") ?? ""))
  const [myInput, setMyInput] = useState("")
  const [mySuggestions, setMySuggestions] = useState<{ name: string; slug: string }[]>([])
  const [myTournaments, setMyTournaments] = useState<Tournament[]>([])
  const [myLoading, setMyLoading] = useState(false)
  const [myError, setMyError] = useState<string | null>(null)
  const [myHistory, setMyHistory] = useState<HistoryEntry[]>([])
  const [matchResults, setMatchResults] = useState<Record<string, MatchResult>>({})
  const [historyLoading, setHistoryLoading] = useState(false)
  const [playerStats, setPlayerStats] = useState<{ rank: number | null; points: number | null; apn: string | null; matchesPlayed: number | null; matchesWon: number | null; matchesLost: number | null }>({ rank: null, points: null, apn: null, matchesPlayed: null, matchesWon: null, matchesLost: null })

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
      setMyError("Abfrage fehlgeschlagen. Nochmal.")
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
    void fetchHistory(slug)
  }

  // Load a profile for viewing without overwriting localStorage
  function viewProfile(name: string, slug: string) {
    setMySlug(slug)
    setMyName(name)
    setMyInput("")
    setMySuggestions([])
    void fetchMyTournaments(slug)
    void fetchHistory(slug)
  }

  // Load any player by slug — fetches history and derives name from the response
  async function loadPlayerBySlug(slug: string) {
    setMySlug(slug)
    setMyInput("")
    setMySuggestions([])
    void fetchMyTournaments(slug)
    setHistoryLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/tournaments/player/history?slug=${encodeURIComponent(slug)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      if (data.name) setMyName(data.name)
      setMyHistory(data.history ?? [])
      setMatchResults(data.match_results ?? {})
      setPlayerStats({ rank: data.rank ?? null, points: data.points ?? null, apn: data.apn ?? null, matchesPlayed: data.matches_played ?? null, matchesWon: data.matches_won ?? null, matchesLost: data.matches_lost ?? null })
    } catch {
      setMyHistory([])
      setMatchResults({})
    } finally {
      setHistoryLoading(false)
    }
  }

  async function fetchHistory(slug: string) {
    setHistoryLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/tournaments/player/history?slug=${encodeURIComponent(slug)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setMyHistory(data.history ?? [])
      setMatchResults(data.match_results ?? {})
      setPlayerStats({ rank: data.rank ?? null, points: data.points ?? null, apn: data.apn ?? null, matchesPlayed: data.matches_played ?? null, matchesWon: data.matches_won ?? null, matchesLost: data.matches_lost ?? null })
    } catch {
      setMyHistory([])
      setMatchResults({})
    } finally {
      setHistoryLoading(false)
    }
  }

  function clearMyProfile() {
    setMySlug("")
    setMyName("")
    setMyInput("")
    setMySuggestions([])
    setMyTournaments([])
    setMyHistory([])
    setMatchResults({})
    localStorage.removeItem(MY_SLUG_KEY)
    localStorage.removeItem(MY_SLUG_KEY + "_name")
  }

  useEffect(() => {
    if (opts?.skipInitialLoad) return
    if (mySlug) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void fetchMyTournaments(mySlug)
      void fetchHistory(mySlug)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return {
    mySlug, myName, myInput, mySuggestions, myTournaments, myLoading, myError,
    myHistory, matchResults, historyLoading,
    searchMyName, selectPlayer, viewProfile, loadPlayerBySlug, clearMyProfile, fetchHistory, playerStats,
  }
}
