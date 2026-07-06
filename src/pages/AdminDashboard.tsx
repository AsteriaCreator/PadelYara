/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from "react"
import { fetchAnalytics, fetchAnalyticsTrends, fetchAnalyticsInsights, fetchSubscriberCount, fetchAlertCount, fetchAlertList, fetchEmailStats, fetchSearchConsole, fetchMySessions, saveMySessions, getSessionId, hasAdminToken, setAdminToken, clearAdminToken } from "../api"
import type { AlertSubscriber, EmailStats } from "../api"
import "./AdminDashboard.css"

function AdminLogin({ onSubmit, error }: { onSubmit: (token: string) => void; error: string | null }) {
  const [value, setValue] = useState("")
  return (
    <div className="admin-state admin-login">
      <form
        className="admin-login-form"
        onSubmit={(e) => { e.preventDefault(); if (value.trim()) onSubmit(value.trim()) }}
      >
        <h2>🔒 Admin Login</h2>
        <p>Enter your admin secret to view the analytics.</p>
        <input
          type="password"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Admin-Token"
          aria-label="Admin-Token"
        />
        <button type="submit" disabled={!value.trim()}>Log in</button>
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

/** Convert YYYY-MM-DD → D.M.YYYY (European format) */
function formatDate(iso: string, short = false): string {
  const [y, m, d] = iso.split("-")
  return short ? `${parseInt(d)}.${parseInt(m)}.` : `${parseInt(d)}.${parseInt(m)}.${y}`
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
              <div className="bar-date">{formatDate(date, true)}</div>
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
  const [searchConsole, setSearchConsole] = useState<any>(null)
  const [subscriberCount, setSubscriberCount] = useState<number | null>(null)
  const [alertCount, setAlertCount] = useState<number | null>(null)
  const [alertList, setAlertList] = useState<AlertSubscriber[] | null>(null)
  const [emailStats, setEmailStats] = useState<EmailStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [authed, setAuthed] = useState<boolean>(() => hasAdminToken())
  const [loginError, setLoginError] = useState<string | null>(null)
  const [mySessions, setMySessions] = useState<string[] | null>(null) // null = not yet loaded
  const [excludeEnabled, setExcludeEnabled] = useState<boolean>(() => {
    try { return localStorage.getItem("analytics_exclude_me") === "true" } catch { return false }
  })

  const excludeIds = excludeEnabled ? (mySessions ?? []) : []

  // Load server-stored session list whenever we become authed
  useEffect(() => {
    if (!authed) return
    fetchMySessions().then(setMySessions).catch(() => setMySessions([]))
  }, [authed])

  useEffect(() => {
    if (!authed) return
    if (mySessions === null) return // wait until sessions are loaded
    // Guard against out-of-order resolution: if the exclude list changes while a
    // fetch is in flight, ignore the stale response so it can't overwrite a newer one.
    let cancelled = false
    // Don't wipe data — keep old values visible while refreshing so the
    // toggle button stays on screen and the user sees the change immediately.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setError(null)
    setRefreshing(true)
    Promise.all([fetchAnalytics(excludeIds), fetchAnalyticsTrends(excludeIds), fetchAnalyticsInsights(excludeIds), fetchSubscriberCount(), fetchAlertCount(), fetchAlertList()])
      .then(([s, t, i, sc, ac, al]) => {
        if (cancelled) return
        setSummary(s); setTrends(t); setInsights(i); setSubscriberCount(sc as number); setAlertCount(ac as number); setAlertList(al as AlertSubscriber[])
      })
      .catch((e: Error) => {
        if (cancelled) return
        // Wrong / expired token → drop it and show the login form again.
        if (e.message === "Unauthorized") {
          clearAdminToken()
          setAuthed(false)
          setLoginError("Wrong secret — please try again.")
        } else {
          setError(e.message)
        }
      })
      .finally(() => { if (!cancelled) setRefreshing(false) })
    // Email stats + GSC load independently so a failure there never breaks the rest of the dashboard.
    fetchEmailStats().then((v) => { if (!cancelled) setEmailStats(v) }).catch(() => { if (!cancelled) setEmailStats(null) })
    fetchSearchConsole().then((v) => { if (!cancelled) setSearchConsole(v) }).catch(() => { if (!cancelled) setSearchConsole(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  async function toggleExclude() {
    let sessions = mySessions ?? []
    if (sessions.length === 0) {
      const id = getSessionId()
      sessions = [id]
      setMySessions(sessions)
      await saveMySessions(sessions)
    }
    const next = !excludeEnabled
    setExcludeEnabled(next)
    try { localStorage.setItem("analytics_exclude_me", String(next)) } catch { /* */ }
  }

  async function handleAddDevice() {
    const id = getSessionId()
    const current = mySessions ?? []
    if (current.includes(id)) return
    const updated = [...current, id]
    setMySessions(updated)
    await saveMySessions(updated)
    if (!excludeEnabled) {
      setExcludeEnabled(true)
      try { localStorage.setItem("analytics_exclude_me", "true") } catch { /* */ }
    }
  }

  async function handleRemoveSession(id: string) {
    const updated = (mySessions ?? []).filter((s) => s !== id)
    setMySessions(updated)
    await saveMySessions(updated)
  }

  const thisDeviceId = getSessionId()
  const thisDeviceRegistered = (mySessions ?? []).includes(thisDeviceId)

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
          <a
            className="admin-logout-btn"
            href="https://vercel.com/mayerconny-4802s-projects/neo-padel-checker/analytics"
            target="_blank"
            rel="noopener noreferrer"
            title="Vercel's own (independent, bot-filtered) analytics for cross-checking"
          >
            📈 Vercel Analytics ↗
          </a>
          <button type="button" className="admin-logout-btn" onClick={handleLogout} title="Abmelden">
            🔓 Abmelden
          </button>
          <div className="exclude-me-toggle">
            <button
              type="button"
              role="switch"
              aria-checked={excludeEnabled && (mySessions ?? []).length > 0}
              className={`exclude-switch ${excludeEnabled && (mySessions ?? []).length > 0 ? "on" : ""}`}
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
                : excludeEnabled && (mySessions ?? []).length > 0
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
          {(mySessions ?? []).length === 0 ? (
            <p className="my-devices-empty">
              No devices added yet. Click "Add this device" on each device you use for testing.
            </p>
          ) : (
            <ul className="my-devices-list">
              {(mySessions ?? []).map((id, i) => (
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
        <h2>Today at a Glance <span className="data-source-label">📊 Own Analytics</span></h2>
        <div className="stats-grid">
          <StatCard
            emoji="🎯" label="Real Visitors" value={summary.engaged_sessions_today ?? 0}
            tip="Visitors who actually searched or clicked 'Book' today. Bots never do that — so this is your most trustworthy count of real people. Trust this number over 'Visitors Today'."
            color="#22c55e" delta={d.engaged_sessions}
          />
          <StatCard
            emoji="🇦🇹" label="AT/DE/CH Visitors" value={summary.dach_sessions_today ?? 0}
            tip="Distinct visitors from Austria, Germany and Switzerland today — your target market. Filters out most bots, which usually report a US location."
            color="#6366f1"
          />
          <StatCard
            emoji="👥" label="Visitors Today (raw)" value={summary.unique_sessions_today}
            tip="Every browser that loaded a page, including bots that run JavaScript. This number is inflated — many are single-page bot visits (often US mobile). Use 'Real Visitors' for the honest count."
            color="#94a3b8" delta={d.unique_sessions}
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
          {alertCount !== null && (
            <StatCard
              emoji="🔔" label="Jagd-Alarm" value={alertCount}
              tip="Confirmed Jagd-Alarm subscriptions — users who get emailed when new tournaments match their filters."
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

      {/* Jagd-Alarm subscribers */}
      {alertList && alertList.length > 0 && (
        <section className="admin-section">
          <h2>🔔 Jagd-Alarm Abonnenten</h2>
          <p className="section-hint">{alertList.filter(a => a.confirmed).length} bestätigt · {alertList.filter(a => !a.confirmed).length} ausstehend</p>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr style={{ color: "#6b7280", textAlign: "left", borderBottom: "1px solid rgba(107,114,128,0.2)" }}>
                <th style={{ padding: "6px 8px" }}>E-Mail</th>
                <th style={{ padding: "6px 8px" }}>Filter</th>
                <th style={{ padding: "6px 8px" }}>Status</th>
                <th style={{ padding: "6px 8px" }}>Zuletzt benachrichtigt</th>
              </tr>
            </thead>
            <tbody>
              {alertList.map((a, i) => {
                const filterParts = [
                  ...(a.filters.bundesland ?? []),
                  ...(a.filters.category ?? []),
                  ...(a.filters.competition ?? []),
                  ...(a.filters.weekday ?? []),
                  ...(a.filters.venue_name ?? []),
                ]
                return (
                  <tr key={i} style={{ borderBottom: "1px solid rgba(107,114,128,0.1)", color: a.confirmed ? "#d1d5db" : "#6b7280" }}>
                    <td style={{ padding: "6px 8px" }}>{a.email}</td>
                    <td style={{ padding: "6px 8px", color: "#9ca3af" }}>{filterParts.length ? filterParts.join(" · ") : "Alle"}</td>
                    <td style={{ padding: "6px 8px" }}>
                      <span style={{ color: a.confirmed ? "#d4f53c" : "#6b7280" }}>{a.confirmed ? "✓ Bestätigt" : "Ausstehend"}</span>
                    </td>
                    <td style={{ padding: "6px 8px", color: "#6b7280" }}>{a.last_notified_at ? new Date(a.last_notified_at).toLocaleDateString("de-AT") : "—"}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>
      )}

      {/* Jagd-Alarm email stats */}
      {emailStats && (
        <section className="admin-section">
          <h2>📧 Jagd-Alarm E-Mail Performance <span className="period-hint">last 30 days</span></h2>
          <p className="section-hint">Opens and clicks tracked by Brevo for all transactional alert emails.</p>
          <div className="stats-grid">
            <StatCard emoji="📤" label="Sent" value={emailStats.requests}
              tip="Total alert emails sent in the last 30 days." color="#6366f1" />
            <StatCard emoji="📬" label="Delivered" value={emailStats.delivered}
              tip="Emails that actually reached the inbox." color="#22c55e" />
            <StatCard emoji="👁️" label="Unique Opens" value={emailStats.uniqueOpens}
              tip={`${emailStats.delivered > 0 ? Math.round((emailStats.uniqueOpens / emailStats.delivered) * 100) : 0}% open rate — how many recipients opened the email at least once.`}
              color="#f59e0b" />
            <StatCard emoji="🖱️" label="Unique Clicks" value={emailStats.uniqueClicks}
              tip={`${emailStats.uniqueOpens > 0 ? Math.round((emailStats.uniqueClicks / emailStats.uniqueOpens) * 100) : 0}% click-to-open rate — of those who opened, how many clicked a link.`}
              color="#d4f53c" />
          </div>
          {emailStats.delivered > 0 && (
            <div style={{ marginTop: 16, display: "flex", gap: 24, fontSize: 13, color: "#9ca3af" }}>
              <span>Open rate: <strong style={{ color: "#f59e0b" }}>{Math.round((emailStats.uniqueOpens / emailStats.delivered) * 100)}%</strong></span>
              <span>Click rate: <strong style={{ color: "#d4f53c" }}>{Math.round((emailStats.uniqueClicks / emailStats.delivered) * 100)}%</strong></span>
              <span>Total opens: {emailStats.opens} &nbsp;·&nbsp; Total clicks: {emailStats.clicks}</span>
            </div>
          )}
        </section>
      )}

      {/* What did people do? */}
      <section className="admin-section">
        <h2>What Did People Do Today? <span className="data-source-label">📊 Own Analytics</span></h2>
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
        <h2>📅 Activity This Week <span className="data-source-label">📊 Own Analytics</span></h2>
        <p className="section-hint">
          Each bar shows how many actions happened that day. Hover over a bar to see the exact number.
        </p>
        <BarChart dates={trends.dates} series={eventSeries} />
      </section>

      {/* 7-day visitors chart */}
      <section className="admin-section">
        <h2>👥 Unique Visitors This Week <span className="data-source-label">📊 Own Analytics</span></h2>
        <p className="section-hint">
          How many different people visited each day. One person = one bar, no matter how many searches they did.
        </p>
        <BarChart dates={trends.dates} series={sessionSeries} />
      </section>

      {/* 7-day pageviews chart */}
      <section className="admin-section">
        <h2>📄 Page Views This Week <span className="data-source-label">📊 Own Analytics</span></h2>
        <p className="section-hint">
          Total page opens per day — counts everyone, including visitors who never search.
        </p>
        <BarChart dates={trends.dates} series={pageviewSeries} />
      </section>

      {/* Where does traffic come from? */}
      {insights && insights.top_referrers && insights.top_referrers.length > 0 && (
        <section className="admin-section">
          <h2>🔗 Where Does Traffic Come From? <span className="period-hint">last 30 days</span> <span className="data-source-label">📊 Own Analytics</span></h2>
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
          <h2>📑 Most-Viewed Pages <span className="period-hint">last 30 days</span> <span className="data-source-label">📊 Own Analytics</span></h2>
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
          <h2>🌍 Where Are Visitors From? <span className="period-hint">last 30 days</span> <span className="data-source-label">📊 Own Analytics</span></h2>
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
          <h2>🏆 Most Booked Venues <span className="period-hint">last 30 days</span> <span className="data-source-label">📊 Own Analytics</span></h2>
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
          <h2>📍 Where Are People Searching? <span className="period-hint">last 30 days</span> <span className="data-source-label">📊 Own Analytics</span></h2>
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
          <h2>🚫 Searches With No Results <span className="period-hint">last 30 days</span> <span className="data-source-label">📊 Own Analytics</span></h2>
          <p className="section-hint">
            <strong>{insights.zero_results_total}</strong> searches found zero courts — these locations have demand but no venue coverage yet. Good candidates for adding new venues.
          </p>
          {insights.zero_results_locations.filter((r: any) => r.location).length > 0 && (
            <div className="event-breakdown">
              {insights.zero_results_locations
                .filter((r: any) => r.location && r.location !== "Ort nicht angegeben" && r.location !== "Location not specified")
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
          <h2>🕐 When Do People Search? <span className="period-hint">last 30 days</span> <span className="data-source-label">📊 Own Analytics</span></h2>
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
          <h2>📱 Mobile vs Desktop <span className="period-hint">last 30 days</span> <span className="data-source-label">📊 Own Analytics</span></h2>
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

      {/* Google Search Console */}
      <section className="admin-section">
        <div className="data-source-label">🔎 Google Search Console</div>
        <h2>🔎 Google Search Console <span className="period-hint">last 28 days</span> <span className="data-source-label">🔎 Google Search Console</span></h2>
        <p className="section-hint">What people search for on Google before finding PadelYara — clicks, impressions, and your average ranking position.</p>

        {searchConsole === null && (
          <p className="section-hint" style={{ color: "#94a3b8" }}>⏳ Loading…</p>
        )}
        {searchConsole === false && (
          <p className="section-hint" style={{ color: "#ef4444" }}>
            ⚠️ Could not load data. Check that <code>GOOGLE_SERVICE_ACCOUNT_JSON</code> is set in Railway and that the service account email is added as a user in Search Console.
          </p>
        )}

        {searchConsole && (() => {
          const hasData = searchConsole.daily?.length > 0 || searchConsole.top_queries?.length > 0
          if (!hasData) return (
            <p className="section-hint" style={{ color: "#94a3b8" }}>
              No data yet — Google hasn't recorded any search impressions for this site in the last 28 days.
              This will fill in once Google indexes more pages and people start finding the site via search.
            </p>
          )
          return (
          <>
          {/* 28-day clicks + impressions trend */}
          {searchConsole.daily && searchConsole.daily.length > 0 && (() => {
            const maxImpr = Math.max(...searchConsole.daily.map((d: any) => d.impressions), 1)
            return (
              <div className="sc-trend">
                {searchConsole.daily.map((d: any) => (
                  <div key={d.date} className="sc-trend-col" title={`${d.date}: ${d.clicks} clicks, ${d.impressions} impressions`}>
                    <div className="sc-trend-bar-bg">
                      <div className="sc-trend-bar-impr" style={{ height: `${Math.round((d.impressions / maxImpr) * 100)}%` }} />
                      <div className="sc-trend-bar-clicks" style={{ height: `${Math.round((d.clicks / maxImpr) * 100)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )
          })()}
          <div className="sc-legend">
            <span className="legend-item"><span className="legend-dot" style={{ background: "#6366f1" }} />Impressions</span>
            <span className="legend-item"><span className="legend-dot" style={{ background: "#22c55e" }} />Clicks</span>
          </div>

          {/* Top queries */}
          {searchConsole.top_queries?.length > 0 && (
            <>
              <h3 className="sc-subhead">Top Search Queries</h3>
              <div className="event-breakdown">
                {searchConsole.top_queries.map(({ query, clicks, impressions, ctr, position }: any) => {
                  const max = searchConsole.top_queries[0].impressions
                  const pct = Math.round((impressions / max) * 100)
                  return (
                    <div key={query} className="event-row">
                      <span className="event-emoji">🔍</span>
                      <div className="event-info">
                        <div className="event-name">{query}</div>
                        <div className="event-bar-bg">
                          <div className="event-bar-fill" style={{ width: `${pct}%`, background: "#6366f1" }} />
                        </div>
                      </div>
                      <span className="sc-meta">{clicks} clicks</span>
                      <span className="sc-meta sc-ctr">{ctr}% CTR</span>
                      <span className="sc-meta sc-pos">#{Math.round(position)}</span>
                    </div>
                  )
                })}
              </div>
            </>
          )}

          {/* Top countries from GSC */}
          {searchConsole.top_countries?.length > 0 && (
            <>
              <h3 className="sc-subhead">Countries (Google Search)</h3>
              <div className="event-breakdown">
                {searchConsole.top_countries.map(({ country, clicks, impressions }: any) => {
                  const max = searchConsole.top_countries[0].impressions
                  const pct = Math.round((impressions / max) * 100)
                  return (
                    <div key={country} className="event-row">
                      <span className="event-emoji">🌍</span>
                      <div className="event-info">
                        <div className="event-name">{country}</div>
                        <div className="event-bar-bg">
                          <div className="event-bar-fill" style={{ width: `${pct}%`, background: "#14b8a6" }} />
                        </div>
                      </div>
                      <span className="sc-meta">{clicks} clicks</span>
                    </div>
                  )
                })}
              </div>
            </>
          )}
          </>
          )
        })()}
      </section>

      {/* Day-by-day table */}
      <section className="admin-section">
        <h2>📋 Day-by-Day Breakdown <span className="data-source-label">📊 Own Analytics</span></h2>
        <p className="section-hint">Your own site data — recorded directly by PadelYara every time someone visits or searches. Not related to Google Search Console.</p>
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
                  <td className="date-cell">{formatDate(date)}</td>
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
