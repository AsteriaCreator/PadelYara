import type { CourtType } from "./types"

export const COURT_TYPES: CourtType[] = ["both", "indoor", "outdoor"]

export const TIME_SLOTS: string[] = [
  "07:00", "08:00", "09:00", "10:00", "11:00", "12:00",
  "13:00", "14:00", "15:00", "16:00", "17:00", "18:00",
  "19:00", "20:00", "21:00", "22:00",
]

// Play-duration picker (minutes → label). Multi-select; 2 h is the default.
// Keep in sync with Backend/availability.py SELECTABLE_DURATIONS.
export const DURATION_OPTIONS: { value: number; label: string }[] = [
  { value: 60,  label: "1 Std" },
  { value: 90,  label: "1,5 Std" },
  { value: 120, label: "2 Std" },
]

export const DEFAULT_DURATIONS: number[] = [120]
