import type { CourtType } from "./types"

export const COURT_TYPES: CourtType[] = ["both", "indoor", "outdoor"]

// Half-hour granularity: venues book on :00 and :30 grids, and 1.5 h games end
// on the half hour. Players can therefore start a search at any half hour.
export const TIME_SLOTS: string[] = [
  "07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00", "10:30",
  "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
  "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00", "18:30",
  "19:00", "19:30", "20:00", "20:30", "21:00", "21:30", "22:00", "22:30",
]

// Play-duration picker (minutes → label). Multi-select; 2 h is the default.
// Keep in sync with Backend/availability.py SELECTABLE_DURATIONS.
export const DURATION_OPTIONS: { value: number; label: string }[] = [
  { value: 60,  label: "1 Std" },
  { value: 90,  label: "1,5 Std" },
  { value: 120, label: "2 Std" },
]

export const DEFAULT_DURATIONS: number[] = [120]

// Dein Match level scale — finer-grained than the Turnierjagd categories, and
// deliberately without "Newcomer". Keep in sync with Backend/matches_mongo.py LEVELS.
export const MATCH_LEVELS: string[] = [
  "Starter", "Starter +", "Starter ++",
  "Low Advanced", "Mid Advanced", "High Advanced",
  "Expert", "Professional", "Elite",
]
