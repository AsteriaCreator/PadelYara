import { lazy, Suspense, useEffect } from "react"
import { Routes, Route, useLocation } from "react-router-dom"
import { trackPageview } from "./api"
import LoadingCat from "./components/LoadingCat"
import PageShell from "./components/PageShell"
import FinderPage from "./pages/FinderPage"

const AdminDashboard   = lazy(() => import("./pages/AdminDashboard"))
const TurnierjagerPage = lazy(() => import("./pages/TurnierjagerPage"))
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
    <Suspense fallback={<LoadingCat />}>
      <Routes>
        <Route path="/admin"        element={<AdminDashboard />} />
        <Route path="/turnierjaeger" element={<PageShell><TurnierjagerPage /></PageShell>} />
        <Route path="/urteil"       element={<PageShell><UrteilPage /></PageShell>} />
        <Route path="/padelrevier"  element={<PageShell><PadelrevierPage /></PageShell>} />
        <Route path="/court/:slug"  element={<PageShell><CourtDetailPage /></PageShell>} />
        <Route path="/about"        element={<PageShell><AboutSection /></PageShell>} />
        <Route path="/datenschutz"  element={<PageShell><DatenschutzPage /></PageShell>} />
        <Route path="/impressum"    element={<PageShell><ImprintPage /></PageShell>} />
        <Route path="/*"            element={<FinderPage />} />
      </Routes>
    </Suspense>
  )
}
