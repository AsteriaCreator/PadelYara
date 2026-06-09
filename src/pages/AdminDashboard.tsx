import { useEffect, useState } from "react"
import { fetchAnalytics, fetchAnalyticsTrends, fetchAnalyticsInsights, fetchSubscriberCount, getMySessionIds, registerThisDevice, removeMySession, getSessionId, hasAdminToken, setAdminToken, clearAdminToken } from "../api"
import "./AdminDashboard.css"

function AdminLogin({ onSubmit, error }: { onSubmit: (token: string) => void; error: string | null }) {
  const [value, setValue] = useState("")
  return (
    <div className="admin-state admin-login">
      <form
        className="admin-login-form"
        onSubmit={(e) => { e.preventDefault(); if (value.trim()) onSubmit(value.trim()) }}
      >
        <h2>🔒 Admin-Login</h2>
        <p>Gib dein Admin-Geheimnis ein, um die Analytics zu sehen.</p>
        <input
          type="password"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Admin-Token"
          aria-label="Admin-Token"
        />
        <button type="submit" disabled={!value.trim()}>Anmelden</button>
        {error && <p className="admin-login-error">{error}</p>}
      </form>
    </div>
  )
}

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

// Friendly names for raw URL paths shown in "Most-Viewed Pages".
function pageLabel(path: string): string {
  const clean = (path || "/").split("?")[0].replace(/\/+$/, "") || "/"
  const STATIC: Record<string, string> = {
    "/": "Startseite (Platzsuche)",
    "/courtfinder": "Startseite (Platzsuche)",
    "/turnierjaeger": "Turnierjäger",
    "/padelrevier": "Padelrevier (Karte)",
    "/about": "Über uns",
    "/datenschutz": "Datenschutz",
    "/admin": "Admin-Dashboard",
  }
  if (STATIC[clean]) return STATIC[clean]
  if (clean.startsWith("/court/")) {
    const slug = clean.slice("/court/".length)
    return `Court-Detail: ${slug}`
  }
  return clean
}

/** Convert a venue slug like "padelzone-traiskirchen" → "Padelzone Traiskirchen" */
function slugToTitle(slug: string): string {
  return (slug || "")
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
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
  const [insights, setInsights] = useState<any>(null)
  const [subscriberCount, setSubscriberCount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [authed, setAuthed] = useState<boolean>(() => hasAdminToken())
  const [loginError, setLoginError] = useState<string | null>(null)
  const [mySessions, setMySessions] = useState<string[]>(() => getMySessionIds())
  const [excludeEnabled, setExcludeEnabled] = useState<boolean>(() => {
    try { return localStorage.getItem("analytics_exclude_me") === "true" } catch { return false }
  })

  const excludeIds = excludeEnabled ? mySessions : []

  useEffect(() => {
    if (!authed) return
    // Don't wipe data — keep old values visible while refreshing so the
    // toggle button stays on screen and the user sees the change immediately.
    setError(null)
    setRefreshing(true)
    Promise.all([fetchAnalytics(excludeIds), fetchAnalyticsTrends(excludeIds), fetchAnalyticsInsights(excludeIds), fetchSubscriberCount()])
      .then(([s, t, i, sc]) => { setSummary(s); setTrends(t); setInsights(i); setSubscriberCount(sc as number) })
      .catch((e: Error) => {
        // Wrong / expired token → drop it and show the login form again.
        if (e.message === "Unauthorized") {
          clearAdminToken()
          setAuthed(false)
          setLoginError("Falsches Geheimnis — bitte nochmal versuchen.")
        } else {
          setError(e.message)
        }
      })
      .finally(() => setRefreshing(false))
  }, [authed, excludeEnabled, mySessions])

  function handleLogin(token: string) {
    setAdminToken(token)
    setLoginError(null)
    setAuthed(true)
  }

  function handleLogout() {
    clearAdminToken()
    setSummary(null)
    setTrends(null)
    setInsights(null)
    setAuthed(false)
  }

  function toggleExclude() {
    // If no devices registered yet, add this one first then enable
    let sessions = mySessions
    if (sessions.length === 0) {
      sessions = registerThisDevice()
      setMySessions(sessions)
    }
    const next = !excludeEnabled
    setExcludeEnabled(next)
    try { localStorage.setItem("analytics_exclude_me", String(next)) } catch { /* */ }
  }

  function handleAddDevice() {
    const updated = registerThisDevice()
    setMySessions(updated)
    if (!excludeEnabled) {
      setExcludeEnabled(true)
      try { localStorage.setItem("analytics_exclude_me", "true") } catch { /* */ }
    }
  }

  function handleRemoveSession(id: string) {
    const updated = removeMySession(id)
    setMySessions(updated)
  }

  const thisDeviceId = getSessionId()
  const thisDeviceRegistered = mySessions.includes(thisDeviceId)

  if (!authed)
    return <AdminLogin onSubmit={handleLogin} error={loginError} />
  if (error)
    return (
      <div className="admin-state admin-error">
        ⚠️ Konnte die Analytics nicht laden: {error}
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

  const pageviewSeries = [{
    label: "Page Views",
    color: "#14b8a6",
    data: trends.dates.map((date: string) => trends.pageviews_by_date?.[date] ?? 0),
  }]

  return (
    <div className="admin-dashboard">
      <header className="admin-header">
        <div className="admin-header-row">
          <h1>📊 Analytics Dashboard</h1>
          <button type="button" className="admin-logout-btn" onClick={handleLogout} title="Abmelden">
            🔓 Abmelden
          </button>
          <div className="exclude-me-toggle">
            <button
              type="button"
              role="switch"
              aria-checked={excludeEnabled && mySessions.length > 0}
              className={`exclude-switch ${excludeEnabled && mySessions.length > 0 ? "on" : ""}`}
              onClick={toggleExclude}
              disabled={refreshing}
              title="Turn on to hide your own visits from the stats"
            >
              <span className="exclude-switch-track">
                <span className="exclude-switch-thumb" />
              </span>
              <span className="exclude-switch-text">Exclude my own visits</span>
            </button>
            <p className="exclude-switch-state">
              {refreshing
                ? "⏳ Updating…"
                : excludeEnabled && mySessions.length > 0
                  ? "🙈 Currently ON — your visits are hidden from the numbers below."
                  : "👁️ Currently OFF — your visits are counted in the numbers below."}
            </p>
          </div>
        </div>
        <p className="admin-subtitle">Here's what's happening on PadelYara — today and over the last 7 days.</p>

        {/* My devices panel */}
        <div className="my-devices-panel">
          <div className="my-devices-header">
            <span className="my-devices-label">🖥️ My devices</span>
            {!thisDeviceRegistered && (
              <button className="add-device-btn" onClick={handleAddDevice}>
                ➕ Add this device
              </button>
            )}
          </div>
          {mySessions.length === 0 ? (
            <p className="my-devices-empty">
              No devices added yet. Click "Add this device" on each device you use for testing.
            </p>
          ) : (
            <ul className="my-devices-list">
              {mySessions.map((id, i) => (
                <li key={id} className="my-devices-item">
                  <span className="device-icon">{id === thisDeviceId ? "📱 This device" : `🖥️ Device ${i + 1}`}</span>
                  <span className="device-id">{id.slice(0, 8)}…</span>
                  <button className="remove-device-btn" onClick={() => handleRemoveSession(id)} title="Remove">✕</button>
                </li>
              ))}
            </ul>
          )}
        </div>
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
          <StatCard
            emoji="📄" label="Page Views Today" value={summary.pageviews_today ?? 0}
            tip="Every page open counts as one view — including visitors who never search. The truest measure of raw traffic."
            color="#14b8a6" delta={d.pageviews}
          />
          {summary.avg_response_ms !== null && (
            <StatCard
              emoji="🚀" label="Avg Speed" value={`${summary.avg_response_ms} ms`}
              tip={`How fast the server responds to searches on average. Under 1000 ms is great. Yours is ${summary.avg_response_ms} ms — ${summary.avg_response_ms < 1000 ? "nice and fast! ✅" : "could be improved ⚠️"}`}
              color={summary.avg_response_ms < 1000 ? "#22c55e" : "#f59e0b"}
              delta={d.avg_response_ms} invertDelta
            />
          )}
          {subscriberCount !== null && (
            <StatCard
              emoji="📬" label="Email Subscribers" value={subscriberCount}
              tip="Total email addresses collected via the newsletter signup banner."
              color="#d4f53c"
            />
          )}
        </div>
        <SuccessRate breakdown={breakdown} />

        {/* Conversion funnel */}
        {(() => {
          const searches = breakdown["search_completed"] ?? 0
          const bookings = breakdown["booking_clicked"] ?? 0
          const rate = searches > 0 ? Math.round((bookings / searches) * 100) : null
          const rate30 = insights && insights.searches_30d > 0
            ? Math.round((insights.bookings_30d / insights.searches_30d) * 100)
            : null
          if (searches === 0) return null
          return (
            <div className="funnel-wrap">
              <div className="funnel-title">
                📊 Conversion Funnel — Today
                <Tip text="How many searches lead to someone clicking 'Book'. This is your most important metric — it shows whether people actually find a court they want." />
              </div>
              <div className="funnel-steps">
                <div className="funnel-step">
                  <span className="funnel-emoji">🔍</span>
                  <span className="funnel-label">Searches</span>
                  <span className="funnel-num">{searches}</span>
                  <div className="funnel-bar-bg"><div className="funnel-bar-fill" style={{ width: "100%", background: "#6366f1" }} /></div>
                </div>
                <div className="funnel-arrow">↓ {rate !== null ? `${rate}%` : "—"}</div>
                <div className="funnel-step">
                  <span className="funnel-emoji">📅</span>
                  <span className="funnel-label">Booking Clicks</span>
                  <span className="funnel-num">{bookings}</span>
                  <div className="funnel-bar-bg"><div className="funnel-bar-fill" style={{ width: `${rate ?? 0}%`, background: "#22c55e" }} /></div>
                </div>
              </div>
              {rate30 !== null && (
                <p className="funnel-hint">30-day average: <strong>{rate30}%</strong> of searches lead to a booking click.</p>
              )}
            </div>
          )
        })()}
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

      {/* 7-day pageviews chart */}
      <section className="admin-section">
        <h2>📄 Page Views This Week</h2>
        <p className="section-hint">
          Total page opens per day — counts everyone, including visitors who never search.
        </p>
        <BarChart dates={trends.dates} series={pageviewSeries} />
      </section>

      {/* Where does traffic come from? */}
      {insights && insights.top_referrers && insights.top_referrers.length > 0 && (
        <section className="admin-section">
          <h2>🔗 Where Does Traffic Come From? <span className="period-hint">last 30 days</span></h2>
          <p className="section-hint">Which sites send you visitors. "direct" = typed the URL or opened a bookmark.</p>
          <div className="event-breakdown">
            {insights.top_referrers.map(({ referrer, count }: { referrer: string; count: number }) => {
              const max = insights.top_referrers[0].count
              const pct = Math.round((count / max) * 100)
              return (
                <div key={referrer} className="event-row">
                  <span className="event-emoji">🔗</span>
                  <div className="event-info">
                    <div className="event-name">{referrer}</div>
                    <div className="event-bar-bg">
                      <div className="event-bar-fill" style={{ width: `${pct}%`, background: "#14b8a6" }} />
                    </div>
                  </div>
                  <span className="event-count">{count}</span>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Most-viewed pages */}
      {insights && insights.top_pages && insights.top_pages.length > 0 && (
        <section className="admin-section">
          <h2>📑 Most-Viewed Pages <span className="period-hint">last 30 days</span></h2>
          <p className="section-hint">Which pages get opened the most.</p>
          <div className="event-breakdown">
            {(() => {
              // Merge paths that resolve to the same page (e.g. / and /courtfinder).
              const byLabel = new Map<string, { label: string; count: number; paths: string[] }>()
              for (const { path, count } of insights.top_pages as { path: string; count: number }[]) {
                const label = pageLabel(path)
                const cur = byLabel.get(label)
                if (cur) { cur.count += count; cur.paths.push(path) }
                else byLabel.set(label, { label, count, paths: [path] })
              }
              const rows = [...byLabel.values()].sort((a, b) => b.count - a.count)
              const max = rows[0]?.count ?? 1
              return rows.map(({ label, count, paths }) => {
                const pct = Math.round((count / max) * 100)
                return (
                  <div key={label} className="event-row">
                    <span className="event-emoji">📄</span>
                    <div className="event-info">
                      <div className="event-name" title={paths.join(", ")}>{label}</div>
                      <div className="event-bar-bg">
                        <div className="event-bar-fill" style={{ width: `${pct}%`, background: "#6366f1" }} />
                      </div>
                    </div>
                    <span className="event-count">{count}</span>
                  </div>
                )
              })
            })()}
          </div>
        </section>
      )}

      {/* Geography */}
      {insights && insights.top_countries && insights.top_countries.length > 0 && (
        <section className="admin-section">
          <h2>🌍 Where Are Visitors From? <span className="period-hint">last 30 days</span></h2>
          <p className="section-hint">Countries your visitors come from, based on their IP address. Only the country name is stored — no IPs.</p>
          <div className="event-breakdown">
            {insights.top_countries.map(({ country, count }: { country: string; count: number }) => {
              const max = insights.top_countries[0].count
              const pct = Math.round((count / max) * 100)
              return (
                <div key={country} className="event-row">
                  <span className="event-emoji">🌍</span>
                  <div className="event-info">
                    <div className="event-name">{country}</div>
                    <div className="event-bar-bg">
                      <div className="event-bar-fill" style={{ width: `${pct}%`, background: "#6366f1" }} />
                    </div>
                  </div>
                  <span className="event-count">{count}</span>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Most booked venues */}
      {insights && insights.top_venues && insights.top_venues.length > 0 && (
        <section className="admin-section">
          <h2>🏆 Most Booked Venues <span className="period-hint">last 30 days</span></h2>
          <p className="section-hint">Which courts people click "Book" on most — useful for knowing who to approach for partnerships.</p>
          <div className="event-breakdown">
            {insights.top_venues.map(({ venue, count }: { venue: string; count: number }) => {
              const max = insights.top_venues[0].count
              const pct = Math.round((count / max) * 100)
              return (
                <div key={venue} className="event-row">
                  <span className="event-emoji">🏆</span>
                  <div className="event-info">
                    <div className="event-name">{slugToTitle(venue)}</div>
                    <div className="event-bar-bg">
                      <div className="event-bar-fill" style={{ width: `${pct}%`, background: "#22c55e" }} />
                    </div>
                  </div>
                  <span className="event-count">{count}</span>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Popular search locations */}
      {insights && insights.top_locations.length > 0 && (
        <section className="admin-section">
          <h2>📍 Where Are People Searching? <span className="period-hint">last 30 days</span></h2>
          <p className="section-hint">The locations users typed in — which areas get the most searches.</p>
          <div className="event-breakdown">
            {insights.top_locations.map(({ location, count }: { location: string; count: number }) => {
              const max = insights.top_locations[0].count
              const pct = Math.round((count / max) * 100)
              return (
                <div key={location} className="event-row">
                  <span className="event-emoji">📍</span>
                  <div className="event-info">
                    <div className="event-name">{location}</div>
                    <div className="event-bar-bg">
                      <div className="event-bar-fill" style={{ width: `${pct}%`, background: "#6366f1" }} />
                    </div>
                  </div>
                  <span className="event-count">{count}</span>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Zero-results searches — demand without coverage */}
      {insights && insights.zero_results_total > 0 && (
        <section className="admin-section">
          <h2>🚫 Searches With No Results <span className="period-hint">last 30 days</span></h2>
          <p className="section-hint">
            <strong>{insights.zero_results_total}</strong> searches found zero courts — these locations have demand but no venue coverage yet. Good candidates for adding new venues.
          </p>
          {insights.zero_results_locations.filter((r: any) => r.location).length > 0 && (
            <div className="event-breakdown">
              {insights.zero_results_locations
                .filter((r: any) => r.location && r.location !== "Ort nicht angegeben")
                .map(({ location, count }: { location: string; count: number }) => {
                  const max = insights.zero_results_locations[0].count
                  const pct = Math.round((count / max) * 100)
                  return (
                    <div key={location} className="event-row">
                      <span className="event-emoji">📍</span>
                      <div className="event-info">
                        <div className="event-name">{location}</div>
                        <div className="event-bar-bg">
                          <div className="event-bar-fill" style={{ width: `${pct}%`, background: "#ef4444" }} />
                        </div>
                      </div>
                      <span className="event-count">{count}</span>
                    </div>
                  )
                })}
            </div>
          )}
        </section>
      )}

      {/* Peak hours heatmap */}
      {insights && (
        <section className="admin-section">
          <h2>🕐 When Do People Search? <span className="period-hint">last 30 days</span></h2>
          <p className="section-hint">Which hours of the day get the most searches (Vienna time).</p>
          <div className="hour-chart">
            {insights.hourly_searches.map(({ hour, count }: { hour: number; count: number }) => {
              const max = Math.max(...insights.hourly_searches.map((h: any) => h.count), 1)
              const pct = Math.round((count / max) * 100)
              const label = `${String(hour).padStart(2, "0")}:00`
              return (
                <div key={hour} className="hour-col" title={`${label}: ${count} searches`}>
                  <div className="hour-bar-bg">
                    <div className="hour-bar-fill" style={{ height: `${pct}%`, background: pct > 60 ? "#6366f1" : pct > 30 ? "#a5b4fc" : "#e0e7ff" }} />
                  </div>
                  {hour % 3 === 0 && <div className="hour-label">{label}</div>}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Device breakdown */}
      {insights && Object.keys(insights.device_breakdown).length > 0 && (
        <section className="admin-section">
          <h2>📱 Mobile vs Desktop <span className="period-hint">last 30 days</span></h2>
          <p className="section-hint">What kind of device people use to search.</p>
          <div className="event-breakdown">
            {Object.entries(insights.device_breakdown as Record<string, number>).map(([device, count]) => {
              const total = Object.values(insights.device_breakdown as Record<string, number>).reduce((a, b) => a + b, 0)
              const pct = Math.round((count / total) * 100)
              const emoji = device === "mobile" ? "📱" : device === "tablet" ? "🗒️" : "🖥️"
              const label = device === "mobile" ? "Mobile" : device === "tablet" ? "Tablet" : "Desktop"
              return (
                <div key={device} className="event-row">
                  <span className="event-emoji">{emoji}</span>
                  <div className="event-info">
                    <div className="event-name">{label}</div>
                    <div className="event-bar-bg">
                      <div className="event-bar-fill" style={{ width: `${pct}%`, background: "#f59e0b" }} />
                    </div>
                  </div>
                  <span className="event-count">{count}</span>
                  <span className="event-pct">{pct}%</span>
                </div>
              )
            })}
          </div>
        </section>
      )}

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
