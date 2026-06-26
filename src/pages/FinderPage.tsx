import { useState } from "react"
import { NavLink } from "react-router-dom"
import { useCourtSearch, ET_BATCH } from "../hooks/useCourtSearch"
import { BG_STYLE } from "../styles"
import Nav from "../components/Nav"
import SearchCard from "../components/SearchCard"
import VenueRow from "../components/VenueRow"
import SkeletonRow from "../components/SkeletonRow"
import LoadingCat from "../components/LoadingCat"
import ImprintModal from "../components/ImprintModal"
import NewsletterBanner from "../components/NewsletterBanner"
import ShareButton from "../components/ShareButton"

const FEEDBACK_EMAIL = "yara@adventure-it.at"

export default function FinderPage() {
  const {
    urlLocation, urlDate, urlTime, urlRadius, urlDurations,
    filteredResults, isLoading, isLoadingMore, hasMore,
    error, searched, pollingActive, lastUpdated, secondsSince,
    bookingWindowNotice, searchLabel, searchWeather, highlightId,
    courtFilter, setCourtFilter, statusFilter, setStatusFilter,
    lastParams, skeletonCount,
    onSearch, onLoadMore, getWeatherHint,
  } = useCourtSearch()

  const [showImprint, setShowImprint] = useState(false)

  return (
    <div className="min-h-screen overflow-x-hidden" style={BG_STYLE}>
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="mb-6">
          <img src="/lockup-horizontal-dark.svg" alt="PadelYara" className="h-24 w-auto block" />
        </div>

        <Nav />

        <p
          className="text-base italic mb-4 mt-2"
          style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#d4f53c" }}
        >
          Yara findet einen freien Court für dich. Wo willst du spielen?
        </p>

        <SearchCard
          onSearch={onSearch}
          isLoading={isLoading}
          courtFilter={courtFilter}
          onCourtFilterChange={setCourtFilter}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          initialLocation={urlLocation || undefined}
          initialDate={urlDate || undefined}
          initialTime={urlTime || undefined}
          initialRadius={urlRadius || undefined}
          initialDurations={urlDurations.length > 0 ? urlDurations : undefined}
        />

        {!searched && !isLoading && !error && (
          <div className="text-center py-8 text-gray-500 text-sm">
            <img src="/cat-head.svg" alt="Yara" className="h-16 w-auto mx-auto mb-3 opacity-30" />
            <p>Courts jagen. Sag mir wo.</p>
            <div className="flex justify-center gap-6 mt-5">
              {[
                { value: "165", label: "Padel-Anlagen" },
                { value: "309", label: "Courts" },
                { value: "728", label: "Turniere" },
              ].map(({ value, label }) => (
                <div key={label} className="flex flex-col items-center gap-0.5">
                  <span className="text-2xl font-bold" style={{ color: "#d4f53c", fontFamily: "'Barlow Condensed', sans-serif" }}>{value}</span>
                  <span className="text-xs text-gray-600">{label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {searchWeather && (
          <div className="mb-5">
            <p className="text-xs text-gray-500 mb-2 px-1 tracking-wide uppercase">
              Das Wetter in deiner Suchlocation
            </p>
            <div
              className="flex items-center gap-4 px-4 py-3 rounded-xl border text-sm"
              style={{ background: "rgba(212,245,60,0.05)", borderColor: "rgba(212,245,60,0.2)" }}
            >
              <span className="text-3xl leading-none">
                {searchWeather.icon === "sun" ? "☀️"
                  : searchWeather.icon === "cloud" ? "☁️"
                  : searchWeather.icon === "rain" || searchWeather.icon === "drizzle" ? "🌧️"
                  : searchWeather.icon === "snow" ? "❄️"
                  : searchWeather.icon === "thunder" ? "⛈️"
                  : searchWeather.icon === "fog" ? "🌫️"
                  : "🌡️"}
              </span>
              <div className="flex flex-col gap-0.5">
                <span className="text-xl font-bold text-white leading-none">{searchWeather.temp}°C</span>
                <span className="text-gray-400 text-xs">{searchWeather.desc}</span>
              </div>
              <div className="ml-auto text-right">
                <span className="text-blue-400 text-sm font-semibold">{searchWeather.rain_prob}%</span>
                <p className="text-gray-500 text-xs">Regenwahrsch.</p>
                {(() => {
                  const h = getWeatherHint(searchWeather.rain_prob)
                  return h ? <p className={`text-xs font-medium mt-0.5 ${h.color}`}>{h.text}</p> : null
                })()}
              </div>
            </div>
          </div>
        )}

        {(isLoading || pollingActive) && <LoadingCat />}

        {isLoading && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
            {Array.from({ length: skeletonCount }).map((_, i) => <SkeletonRow key={i} />)}
          </div>
        )}

        {searched && !isLoading && searchLabel && (
          <p className="text-xs text-gray-500 mb-1 px-1 tracking-wide uppercase">{searchLabel}</p>
        )}

        {searched && !isLoading && !error && filteredResults.length > 0 && lastParams && (
          <div className="mb-2 px-1 flex items-center justify-between">
            <p style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "0.85rem", color: "rgba(212,245,60,0.65)" }}>
              {filteredResults.length === 1
                ? `1 Ergebnis im Umkreis von ${lastParams.radius} km`
                : `${filteredResults.length} Ergebnisse im Umkreis von ${lastParams.radius} km`}
            </p>
            <ShareButton params={lastParams} />
          </div>
        )}

        {searched && !isLoading && bookingWindowNotice && (
          <p className="text-xs text-gray-500 mb-3 px-1">ℹ️ {bookingWindowNotice}</p>
        )}

        {searched && !isLoading && !error && filteredResults.length > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
            {filteredResults.map((venue) => (
              <VenueRow
                key={venue.id}
                venue={venue}
                pollingActive={pollingActive}
                searchDate={lastParams?.date}
                highlighted={venue.id === highlightId}
              />
            ))}
          </div>
        )}

        {searched && !isLoading && !error && filteredResults.length === 0 && (
          <div className="text-center py-10 mb-4">
            <p className="text-3xl mb-3">🎾</p>
            <p className="text-white font-semibold mb-1">Nichts gefunden.</p>
            <p className="text-gray-500 text-sm mb-4">Lösungsvorschlag: woanders wohnen.</p>
            {lastParams && lastParams.radius < 50 && (
              <button
                onClick={() => onSearch({ ...lastParams!, radius: 50 })}
                className="text-sm font-bold tracking-wide px-5 py-2 rounded-lg transition-colors"
                style={{
                  fontFamily: "'Barlow Condensed', sans-serif",
                  border: "1px solid rgba(212,245,60,0.3)",
                  color: "rgba(212,245,60,0.8)",
                  background: "transparent",
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = "rgba(212,245,60,0.7)"
                  e.currentTarget.style.color = "#d4f53c"
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = "rgba(212,245,60,0.3)"
                  e.currentTarget.style.color = "rgba(212,245,60,0.8)"
                }}
              >
                Auf 50 km erweitern
              </button>
            )}
          </div>
        )}

        {isLoadingMore && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 divide-y divide-gray-800 mb-4">
            {Array.from({ length: ET_BATCH }).map((_, i) => <SkeletonRow key={`more-${i}`} />)}
          </div>
        )}

        {hasMore && !isLoadingMore && !isLoading && searched && (
          <button
            onClick={onLoadMore}
            className="w-full py-3 rounded-xl text-sm font-bold tracking-wide transition-colors mb-4 cursor-pointer"
            style={{ border: "1px solid rgba(212,245,60,0.3)", color: "rgba(212,245,60,0.7)", fontFamily: "'Barlow Condensed', sans-serif", fontSize: "1rem" }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = "rgba(212,245,60,0.7)")}
            onMouseLeave={e => (e.currentTarget.style.borderColor = "rgba(212,245,60,0.3)")}
          >
            MEHR ERGEBNISSE
          </button>
        )}

        {searched && !isLoading && lastUpdated && (
          <p className="text-gray-500 text-xs text-right mb-4">
            Zuletzt aktualisiert {secondsSince < 10 ? "gerade eben" : `vor ${secondsSince} Sekunden`}
          </p>
        )}

        <div className="mt-8">
          <NewsletterBanner />
          <p className="text-xs px-1 mt-3" style={{ color: "#6b7280" }}>
            Einen Platz vermisst?{" "}
            <a
              href={`mailto:${FEEDBACK_EMAIL}?subject=PadelYara%20Feedback`}
              style={{ color: "#9ca3af", textDecoration: "underline" }}
            >
              Sag's mir.
            </a>
          </p>
        </div>
      </div>

      <footer className="text-center py-8 mt-4">
        <p className="text-xs text-gray-500 mb-2 tracking-widest uppercase">PadelYara</p>
        <div className="flex items-center justify-center gap-3 mb-3">
          {[
            { href: "https://www.instagram.com/padelyara", label: "Instagram", path: "M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" },
            { href: "https://www.facebook.com/padelyara", label: "Facebook", path: "M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" },
          ].map(({ href, label, path }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={label}
              className="text-gray-600 transition-colors"
              onMouseEnter={e => (e.currentTarget.style.color = "#d4f53c")}
              onMouseLeave={e => (e.currentTarget.style.color = "")}
            >
              <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                <path d={path} />
              </svg>
            </a>
          ))}
        </div>
        <div className="flex items-center justify-center gap-4">
          <NavLink to="/impressum" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            Impressum
          </NavLink>
          <NavLink to="/datenschutz" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            Datenschutz
          </NavLink>
        </div>
      </footer>

      {showImprint && <ImprintModal onClose={() => setShowImprint(false)} />}
    </div>
  )
}
