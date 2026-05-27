export default function SkeletonRow() {
  return (
    <div className="px-4 py-3 border-b border-gray-700/50 last:border-0 animate-pulse">

      {/* ── Row 1: venue name bar + status badge ───────────────────────────── */}
      {/* gap-3 replaces ml-* margins so browser gap-accounting is consistent.
          Name bar is flex-1 (flex-basis:0, grows into remaining space) — it
          has no intrinsic width to claim, so it physically cannot overflow. */}
      <div className="flex items-center gap-3 mb-2">
        <div className="h-4 bg-gray-700 rounded flex-1" />
        <div className="h-5 bg-gray-700 rounded-full w-20 shrink-0" />
      </div>

      {/* ── Row 2: meta pills + booking button placeholder ─────────────────── */}
      {/* Right side is shrink-0 w-24 (fixed).
          Left side is flex-1 min-w-0 — guaranteed to receive exactly
          (container − 96px − 12px gap) of space, never more.
          Bars inside use percentage widths (w-1/4, w-1/5) relative to that
          resolved flex-1 width, so they can never sum past 100 % of it.
          flex-wrap is a final safety valve: if any bar would overflow it
          wraps to the next line instead of pushing past the right edge. */}
      <div className="flex items-center gap-3">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 flex-1 min-w-0">
          <div className="h-3 bg-gray-800 rounded w-1/4" />
          <div className="h-3 bg-gray-800 rounded w-1/5" />
          <div className="h-3 bg-gray-800 rounded w-1/4" />
        </div>
        <div className="h-6 bg-gray-700 rounded w-24 shrink-0" />
      </div>

    </div>
  )
}
