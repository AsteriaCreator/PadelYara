import { useEffect, useState } from "react"
import { fetchAnalytics, fetchAnalyticsTrends } from "../api"
import "./AdminDashboard.css"

// Plain-English labels for each event type
const EVENT_META: Record<string, { label: string; emoji: string; color: string; tip: string }> = {
  search_completed: {
    label: "Successful Searches",
    emoji: "🔍",
    color: "#22c55e",
    tip: "A user searched for courts and got results back.",
  },
  search_failed: {
    label: "Failed Searches",
    emoji: "❌",
    color: "#ef4444",
    tip: "A user searched but something went wrong (bad input or an error).",
  },
  booking_clicked: {
    label: "Booking Clicks",
    emoji: "📅",
    color: "#3b82f6",
    tip: "A user clicked 'Book' on a court listing.",
  },
  scraper_timeout: {
    label: "Scraper Timeouts",
    emoji: "⏱️",
    color: "#f59e0b",
    tip: "A venue check took too long and was skipped.",
  },
}

function meta(event: string) {
  return EVENT_META[event] ?? { label: event, emoji: "📊", color: "#94a3b8", tip: event }
}

function Tip({ text }: { text: string }) {
  return (
    <span className="tip-wrapper">
      <span className="tip-icon">?</span>
      <span className="tip-bubble">{text}</span>
    </span>
  )
}

function Delta({ value, invertColor = false }: { value: number | null; invertColor?: boolean }) {
  if (value === null || value === undefined) return null
  const isPositive = value > 0
  const isGood = invertColor ? !isPositive : isPositive
  const color = value === 0 ? "#94a3b8" : isGood ? "#22c55e" : "#ef4444"
  const arrow = value === 0 ? "→" : isPositive ? "↑" : "↓"
  return (
    <span className="delta" style={{ color }}>
      {arrow} {Math.abs(value)}% vs yesterday
    </span>
  )
}

function StatCard({
  emoji, label, value, tip, color, delta, invertDelta,
}: {
  emoji: string
  label: string
  value: number | string
  tip: string
  color?: string
  delta?: number | null
  invertDelta?: boolean
}) {
  return (
    <div className="stat-card" style={{ borderTopColor: color ?? "#6366f1" }}>
      <div className="stat-emoji">{emoji}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">
        {label} <Tip text={tip} />
      </div>
      {delta !== undefined && (
        <div className="stat-delta">
          <Delta value={delta ?? null} invertColor={invertDelta} />
        </div>
      )}
    </div>
  )
}

function BarChart({
  dates,
  series,
}: {
  dates: string[]
  series: { label: string; color: string; data: number[] }[]
}) {
  const allValues = series.flatMap((s) => s.data)
  const max = Math.max(...allValues, 1)

  return (
    <div className="bar-chart-wrapper">
      <div className="bar-chart-cols">
        {dates.map((date, i) => {
          const total = series.reduce((sum, s) => sum + s.data[i], 0)
          return (
            <div key={date} className="bar-col">
              <div className="bar-total-label">{total > 0 ? total : ""}</div>
              <div className="bar-stack">
                {[...series].reverse().map((s) => (
                  <div
                    key={s.label}
                    className="bar-segment"
                    style={{ height: `${(s.data[i] / max) * 100}%`, background: s.color }}
                    title={`${s.label}: ${s.data[i]}`}
                  />
                ))}
              </div>
              <div className="bar-date">{date.slice(5)}</div>
            </div>
          )
        })}
      </div>
      <div className="bar-legend">
        {series.map((s) => (
          <span key={s.label} className="legend-item">
            <span className="legend-dot" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  )
}

function SuccessRate({ breakdown }: { breakdown: Record<string, number> }) {
  const ok = breakdown["search_completed"] ?? 0
  const fail = breakdown["search_failed"] ?? 0
  const total = ok + fail
  if (total === 0) return null
  const pct = Math.round((ok / total) * 100)
  const color = pct >= 90 ? "#22c55e" : pct >= 70 ? "#f59e0b" : "#ef4444"
  return (
    <div className="success-rate-wrap">
      <div className="success-rate-bar-bg">
        <div className="success-rate-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="success-rate-label" style={{ color }}>
        {pct}% of searches succeeded today
      </span>
    </div>
  )
}

export default function AdminDashboard() {
  const [summary, setSummary] = useState<any>(null)
  const [trends, setTrends] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([fetchAnalytics(), fetchAnalyticsTrends()])
      .then(([s, t]) => { setSummary(s); setTrends(t) })
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error)
    return (
      <div className="admin-state admin-error">
        🔒 Access denied — make sure <code>VITE_ADMIN_TOKEN</code> is set correctly in your <code>.env.local</code> file.
      </div>
    )
  if (!summary || !trends)
    return <div className="admin-state admin-loading">⏳ Loading analytics…</div>

  const d = summary.deltas
  const breakdown: Record<string, number> = summary.event_breakdown_today

  const eventSeries = trends.event_types.map((evt: string) => ({
    label: meta(evt).label,
    color: meta(evt).color,
    data: trends.dates.map((date: string) => trends.events_by_date[date]?.[evt] ?? 0),
  }))

  const sessionSeries = [{
    label: "Unique Visitors",
    color: "#f59e0b",
    data: trends.dates.map((date: string) => trends.unique_sessions_by_date[date] ?? 0),
  }]

  return (
    <div className="admin-dashboard">
      <header className="admin-header">
        <h1>📊 Analytics Dashboard</h1>
        <p className="admin-subtitle">Here's what's happening on PadelYara — today and over the last 7 days.</p>
      </header>

      {/* Today's numbers */}
      <section className="admin-section">
        <h2>Today at a Glance</h2>
        <div className="stats-grid">
          <StatCard
            emoji="👥" label="Visitors Today" value={summary.unique_sessions_today}
            tip="Each visitor gets a random ID stored in their browser. This counts how many different people visited today."
            color="#6366f1" delta={d.unique_sessions}
          />
          <StatCard
            emoji="🆕" label="First-Time Visitors" value={summary.new_sessions_today}
            tip="People who came to the site for the very first time today."
            color="#22c55e"
          />
          <StatCard
            emoji="🔄" label="Returning Visitors" value={summary.returning_sessions_today}
            tip="People who visited on a previous day and came back again today."
            color="#f59e0b"
          />
          <StatCard
            emoji="⚡" label="Total Actions" value={summary.total_events_today}
            tip="Every search or booking click counts as one action. High numbers mean people are actively using the site."
            color="#3b82f6" delta={d.total_events}
          />
          {summary.avg_response_ms !== null && (
            <StatCard
              emoji="🚀" label="Avg Speed" value={`${summary.avg_response_ms} ms`}
              tip={`How fast the server responds to searches on average. Under 1000 ms is great. Yours is ${summary.avg_response_ms} ms — ${summary.avg_response_ms < 1000 ? "nice and fast! ✅" : "could be improved ⚠️"}`}
              color={summary.avg_response_ms < 1000 ? "#22c55e" : "#f59e0b"}
              delta={d.avg_response_ms} invertDelta
            />
          )}
        </div>
        <SuccessRate breakdown={breakdown} />
      </section>

      {/* What did people do? */}
      <section className="admin-section">
        <h2>What Did People Do Today?</h2>
        <p className="section-hint">
          Every action a user takes is recorded. Here's the breakdown — hover the ? for an explanation.
        </p>
        <div className="event-breakdown">
          {Object.entries(breakdown).map(([evt, count]) => {
            const m = meta(evt)
            const total = Object.values(breakdown).reduce((a, b) => a + b, 0)
            const pct = total > 0 ? Math.round((count / total) * 100) : 0
            const ydayCount = d.events_by_type?.[evt]
            return (
              <div key={evt} className="event-row">
                <span className="event-emoji">{m.emoji}</span>
                <div className="event-info">
                  <div className="event-name">
                    {m.label} <Tip text={m.tip} />
                    {ydayCount !== null && ydayCount !== undefined && (
                      <Delta value={ydayCount} invertColor={evt === "search_failed" || evt === "scraper_timeout"} />
                    )}
                  </div>
                  <div className="event-bar-bg">
                    <div className="event-bar-fill" style={{ width: `${pct}%`, background: m.color }} />
                  </div>
                </div>
                <span className="event-count">{count}</span>
                <span className="event-pct">{pct}%</span>
              </div>
            )
          })}
        </div>
      </section>

      {/* 7-day activity chart */}
      <section className="admin-section">
        <h2>📅 Activity This Week</h2>
        <p className="section-hint">
          Each bar shows how many actions happened that day. Hover over a bar to see the exact number.
        </p>
        <BarChart dates={trends.dates} series={eventSeries} />
      </section>

      {/* 7-day visitors chart */}
      <section className="admin-section">
        <h2>👥 Unique Visitors This Week</h2>
        <p className="section-hint">
          How many different people visited each day. One person = one bar, no matter how many searches they did.
        </p>
        <BarChart dates={trends.dates} series={sessionSeries} />
      </section>

      {/* Day-by-day table */}
      <section className="admin-section">
        <h2>📋 Day-by-Day Breakdown</h2>
        <p className="section-hint">The full numbers for every day — easy to compare at a glance.</p>
        <div className="table-scroll">
          <table className="analytics-table">
            <thead>
              <tr>
                <th>Date</th>
                {trends.event_types.map((e: string) => (
                  <th key={e}>{meta(e).emoji} {meta(e).label}</th>
                ))}
                <th>👥 Unique Visitors</th>
              </tr>
            </thead>
            <tbody>
              {trends.dates.map((date: string) => (
                <tr key={date}>
                  <td className="date-cell">{date}</td>
                  {trends.event_types.map((e: string) => (
                    <td key={e} style={{ color: meta(e).color, fontWeight: 600 }}>
                      {trends.events_by_date[date]?.[e] ?? 0}
                    </td>
                  ))}
                  <td className="sessions-cell">
                    {trends.unique_sessions_by_date[date] ?? 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
