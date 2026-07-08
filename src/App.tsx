import { lazy, Suspense, useEffect, Component, type ReactNode, type ComponentType } from "react"
import * as Sentry from "@sentry/react"
import { Routes, Route, Navigate, useLocation } from "react-router-dom"
import { trackPageview } from "./api"
import LoadingCat from "./components/LoadingCat"
import PageShell from "./components/PageShell"
import FinderPage from "./pages/FinderPage"

// Auto-reload once on chunk fetch failure (stale deploy cache)
function lazyWithReload<T extends ComponentType>(factory: () => Promise<{ default: T }>) {
  return lazy(() =>
    factory().catch(() => {
      window.location.reload()
      return new Promise<never>(() => {})
    })
  )
}

class ErrorBoundary extends Component<{ children: ReactNode }, { crashed: boolean }> {
  state = { crashed: false }
  static getDerivedStateFromError() { return { crashed: true } }
  componentDidCatch(error: Error) { Sentry.captureException(error) }
  render() {
    if (this.state.crashed) return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4 text-center"
        style={{ background: "#080810", fontFamily: "'Barlow Condensed', sans-serif" }}>
        <img src="/cat-head.svg" alt="Yara" className="h-16 w-auto mb-4 opacity-30" />
        <p className="text-white font-bold text-lg tracking-wide mb-1">Offenbar streikt gerade jemand.</p>
        <p className="text-gray-500 text-sm mb-6">Einmal neu laden.</p>
        <button
          onClick={() => window.location.reload()}
          className="px-6 py-2 rounded-lg text-sm font-bold tracking-wide"
          style={{ background: "#d4f53c", color: "#080810" }}
        >
          NEU LADEN
        </button>
      </div>
    )
    return this.props.children
  }
}

const AdminDashboard            = lazyWithReload(() => import("./pages/AdminDashboard"))
const TurnierjagerPage          = lazyWithReload(() => import("./pages/TurnierjagerPage"))
const TurnierjagerMinePage      = lazyWithReload(() => import("./pages/TurnierjagerMinePage"))
const SpielanalysePage          = lazyWithReload(() => import("./pages/SpielanalysePage"))
const TournamentDetailPage      = lazyWithReload(() => import("./pages/TournamentDetailPage"))
const PadelrevierPage           = lazyWithReload(() => import("./pages/PadelrevierPage"))
const PadelrevierCityPage       = lazyWithReload(() => import("./pages/PadelrevierCityPage"))
const PadelquartierPage         = lazyWithReload(() => import("./pages/PadelquartierPage"))
const PadelquartierDetailPage   = lazyWithReload(() => import("./pages/PadelquartierDetailPage"))
const CourtDetailPage           = lazyWithReload(() => import("./pages/CourtDetailPage"))
const DatenschutzPage           = lazyWithReload(() => import("./pages/DatenschutzPage"))
const ImprintPage               = lazyWithReload(() => import("./pages/ImprintPage"))
const AGBPage                   = lazyWithReload(() => import("./pages/AGBPage"))
const AboutSection              = lazyWithReload(() => import("./components/AboutSection"))

export default function App() {
  const location = useLocation()
  useEffect(() => {
    if (location.pathname.startsWith("/admin")) return
    trackPageview(location.pathname)
  }, [location.pathname])

  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingCat />}>
        <Routes>
        <Route path="/admin"        element={<AdminDashboard />} />
        <Route path="/turnierjaeger"           element={<PageShell><TurnierjagerPage /></PageShell>} />
        <Route path="/turnierjaeger/meine"           element={<PageShell><TurnierjagerMinePage /></PageShell>} />
        <Route path="/turnierjaeger/turnier/:sourceId"  element={<PageShell><TournamentDetailPage /></PageShell>} />
        <Route path="/turnierjaeger/spielanalyse"     element={<PageShell><SpielanalysePage /></PageShell>} />
        <Route path="/turnierjaeger/spielanalyse/:slug" element={<PageShell><SpielanalysePage /></PageShell>} />
        <Route path="/turnierjaeger/merkliste"        element={<Navigate to="/turnierjaeger/meine" replace />} />
        <Route path="/turnierjaeger/meine/:slug"      element={<Navigate to="/turnierjaeger/spielanalyse/:slug" replace />} />
        <Route path="/urteil"                         element={<Navigate to="/turnierjaeger/spielanalyse" replace />} />
        <Route path="/padelrevier"        element={<PageShell><PadelrevierPage /></PageShell>} />
        <Route path="/padelrevier/:city"  element={<PageShell><PadelrevierCityPage /></PageShell>} />
        <Route path="/padelquartier"      element={<PageShell><PadelquartierPage /></PageShell>} />
        <Route path="/padelquartier/:slug" element={<PageShell><PadelquartierDetailPage /></PageShell>} />
        <Route path="/court/:slug"  element={<PageShell><CourtDetailPage /></PageShell>} />
        <Route path="/about"        element={<PageShell><AboutSection /></PageShell>} />
        <Route path="/datenschutz"  element={<PageShell><DatenschutzPage /></PageShell>} />
        <Route path="/impressum"    element={<PageShell><ImprintPage /></PageShell>} />
        <Route path="/agb"          element={<PageShell><AGBPage /></PageShell>} />
        <Route path="/*"            element={<FinderPage />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
