import { MATCH_LEVELS } from "../constants"

// ── Level multi-select pills — same visual language as TurnierjagerPage's MultiChip ──

export function LevelPills({
  selected, onChange, allowEmpty = true,
}: {
  selected: string[]
  onChange: (v: string[]) => void
  allowEmpty?: boolean
}) {
  function toggle(level: string) {
    if (selected.includes(level)) {
      if (!allowEmpty && selected.length === 1) return
      onChange(selected.filter(l => l !== level))
    } else {
      onChange([...selected, level])
    }
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {MATCH_LEVELS.map(level => {
        const active = selected.includes(level)
        return (
          <button
            key={level}
            type="button"
            onClick={() => toggle(level)}
            aria-pressed={active}
            className="text-xs px-2.5 py-1 rounded-full border transition-colors"
            style={{
              borderColor: active ? "#d4f53c" : "rgba(107,114,128,0.4)",
              color: active ? "#d4f53c" : "#9ca3af",
              background: active ? "rgba(212,245,60,0.08)" : "transparent",
            }}
          >
            {level}
          </button>
        )
      })}
    </div>
  )
}

// ── Avatar row — organizer marked with a star, org-added guests slightly dimmer ──

export function AvatarRow({ organizerName, players, spotsTotal }: {
  organizerName: string
  players: { name: string; added_by_organizer: boolean }[]
  spotsTotal: number
}) {
  const emptySlots = Math.max(0, spotsTotal - 1 - players.length)
  return (
    <div className="flex gap-1.5 flex-wrap">
      <Avatar label={organizerName} isOrganizer />
      {players.map((p, i) => (
        <Avatar key={i} label={p.name} dim={p.added_by_organizer} />
      ))}
      {Array.from({ length: emptySlots }).map((_, i) => (
        <div key={`empty-${i}`} className="w-8 h-8 rounded-full border border-dashed border-gray-700 grid place-items-center text-gray-600 text-sm">+</div>
      ))}
    </div>
  )
}

function Avatar({ label, isOrganizer, dim }: { label: string; isOrganizer?: boolean; dim?: boolean }) {
  const initial = label.trim().slice(0, 1).toUpperCase() || "?"
  return (
    <div className="relative">
      <div
        className="w-8 h-8 rounded-full grid place-items-center text-sm font-bold"
        style={{ background: dim ? "rgba(212,245,60,0.35)" : "#d4f53c", color: "#080810" }}
        title={label}
      >
        {initial}
      </div>
      {isOrganizer && (
        <span className="absolute -top-1.5 -right-1 text-xs" style={{ color: "#fbbf24" }}>★</span>
      )}
    </div>
  )
}
