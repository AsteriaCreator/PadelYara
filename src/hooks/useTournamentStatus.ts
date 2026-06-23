import { useState, useCallback } from "react"
import type { Tournament } from "../types"

export type TournamentStatusValue =
  | "interessant"
  | "gefragt"
  | "zusage"
  | "ich_buche"
  | "sie_bucht"
  | "warteliste"
  | "gebucht"

export const STATUS_LABELS: Record<TournamentStatusValue, string> = {
  interessant: "Interessant",
  gefragt: "Gefragt",
  zusage: "Zusage",
  ich_buche: "Ich buche",
  sie_bucht: "Partner bucht",
  warteliste: "Warteliste",
  gebucht: "Gebucht",
}

// Auto-detected from padel-austria.at data, shown differently in UI
export const AUTO_STATUSES: TournamentStatusValue[] = ["warteliste", "gebucht"]

const STORAGE_KEY = "tournament_status_v1"

function loadStorage(): Record<string, TournamentStatusValue> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Record<string, TournamentStatusValue>) : {}
  } catch {
    return {}
  }
}

function saveStorage(data: Record<string, TournamentStatusValue>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch {
    // ignore quota errors
  }
}

function tournamentKey(t: Tournament): string {
  return `${t.source}:${t.source_id}`
}

export function useTournamentStatus(): {
  getStatus: (t: Tournament) => TournamentStatusValue
  setStatus: (t: Tournament, s: TournamentStatusValue) => void
  autoSetStatus: (t: Tournament, s: "warteliste" | "gebucht") => void
  clearStatus: (t: Tournament) => void
  allStatuses: Record<string, TournamentStatusValue>
} {
  const [allStatuses, setAllStatuses] = useState<Record<string, TournamentStatusValue>>(loadStorage)

  const persist = useCallback((next: Record<string, TournamentStatusValue>) => {
    setAllStatuses(next)
    saveStorage(next)
  }, [])

  const getStatus = useCallback(
    (t: Tournament): TournamentStatusValue => {
      return allStatuses[tournamentKey(t)] ?? "interessant"
    },
    [allStatuses],
  )

  const setStatus = useCallback(
    (t: Tournament, s: TournamentStatusValue) => {
      persist({ ...allStatuses, [tournamentKey(t)]: s })
    },
    [allStatuses, persist],
  )

  // Only overrides if the current value is "interessant" (the default)
  const autoSetStatus = useCallback(
    (t: Tournament, s: "warteliste" | "gebucht") => {
      const key = tournamentKey(t)
      const current = allStatuses[key] ?? "interessant"
      if (current === "interessant") {
        persist({ ...allStatuses, [key]: s })
      }
    },
    [allStatuses, persist],
  )

  const clearStatus = useCallback(
    (t: Tournament) => {
      const next = { ...allStatuses }
      delete next[tournamentKey(t)]
      persist(next)
    },
    [allStatuses, persist],
  )

  return { getStatus, setStatus, autoSetStatus, clearStatus, allStatuses }
}
