import { lazy, Suspense, useEffect, Component, type ReactNode } from "react"
import { Routes, Route, useLocation } from "react-router-dom"
import { trackPageview } from "./api"
import LoadingCat from "./components/LoadingCat"
import PageShell from "./components/PageShell"
import FinderPage from "./pages/FinderPage"

class ErrorBoundary extends Component<{ children: ReactNode }, { crashed: boolean }> {
  state = { crashed: false }
  static getDerivedStateFromError() { return { crashed: true } }
  render() {
    if (this.state.crashed) return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4 text-center"
        style={{ background: "#080810", fontFamily: "'Barlow Condensed', sans-serif" }}>
        <img src="/cat-head.svg" alt="Yara" className="h-16 w-auto mb-4 opacity-30" />
        <p className="text-white font-bold text-lg tracking-wide mb-1">Seite konnte nicht geladen werden.</p>
        <p className="text-gray-500 text-sm mb-6">Schlechter Empfang? Einmal neu laden.</p>
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

const AdminDashboard            = lazy(() => import("./pages/AdminDashboard"))
const TurnierjagerPage          = lazy(() => import("./pages/TurnierjagerPage"))
const TurnierjagerMinePage      = lazy(() => import("./pages/TurnierjagerMinePage"))
const TurnierjagerMerklistePage = lazy(() => import("./pages/TurnierjagerMerklistePage"))
const UrteilPage       = lazy(() => import("./pages/UrteilPage"))
const PadelrevierPage  = lazy(() => import("./pages/PadelrevierPage"))
const CourtDetailPage  = lazy(() => import("./pages/CourtDetailPage"))
const DatenschutzPage  = lazy(() => import("./pages/DatenschutzPage"))
const ImprintPage      = lazy(() => import("./pages/ImprintPage"))
const AboutSection     = lazy(() => import("./components/AboutSection"))

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
        <Route path="/turnierjaeger/meine"     element={<PageShell><TurnierjagerMinePage /></PageShell>} />
        <Route path="/turnierjaeger/merkliste" element={<PageShell><TurnierjagerMerklistePage /></PageShell>} />
        <Route path="/urteil"       element={<PageShell><UrteilPage /></PageShell>} />
        <Route path="/padelrevier"  element={<PageShell><PadelrevierPage /></PageShell>} />
        <Route path="/court/:slug"  element={<PageShell><CourtDetailPage /></PageShell>} />
        <Route path="/about"        element={<PageShell><AboutSection /></PageShell>} />
        <Route path="/datenschutz"  element={<PageShell><DatenschutzPage /></PageShell>} />
        <Route path="/impressum"    element={<PageShell><ImprintPage /></PageShell>} />
        <Route path="/*"            element={<FinderPage />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
