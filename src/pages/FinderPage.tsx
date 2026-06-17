import { useState } from "react"
import { NavLink } from "react-router-dom"
import { useCourtSearch, ET_BATCH } from "../hooks/useCourtSearch"
import { BG_STYLE } from "../components/PageShell"
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
    lastParamsRef, skeletonCount,
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

        <p className="mb-4 text-xs" style={{ color: "#6b7280" }}>
          PadelYara ist im Aufbau. Etwas fehlt oder stimmt nicht?{" "}
          <a
            href={`mailto:${FEEDBACK_EMAIL}?subject=PadelYara%20Feedback`}
            style={{ color: "#9ca3af", textDecoration: "underline" }}
          >
            Schreib Yara.
          </a>
        </p>

        <NewsletterBanner />

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
          <div className="text-center py-8 text-gray-600 text-sm">
            <img src="/cat-head.svg" alt="Yara" className="h-16 w-auto mx-auto mb-3 opacity-30" />
            <p>Courts jagen. Sag mir wo.</p>
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
                <p className="text-gray-600 text-xs">Regenwahrsch.</p>
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
          <p className="text-xs text-gray-600 mb-1 px-1 tracking-wide uppercase">{searchLabel}</p>
        )}

        {searched && !isLoading && !error && filteredResults.length > 0 && lastParamsRef.current && (
          <div className="mb-2 px-1 flex items-center justify-between">
            <p style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "0.85rem", color: "rgba(212,245,60,0.4)" }}>
              {filteredResults.length === 1
                ? `1 Ergebnis im Umkreis von ${lastParamsRef.current.radius} km`
                : `${filteredResults.length} Ergebnisse im Umkreis von ${lastParamsRef.current.radius} km`}
            </p>
            <ShareButton params={lastParamsRef.current} />
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
                searchDate={lastParamsRef.current?.date}
                highlighted={venue.id === highlightId}
              />
            ))}
          </div>
        )}

        {searched && !isLoading && !error && filteredResults.length === 0 && (
          <div className="text-center py-10 mb-4">
            <p className="text-3xl mb-3">🎾</p>
            <p className="text-white font-semibold mb-1">Keine Ergebnisse.</p>
            <p className="text-gray-500 text-sm">Lösungsvorschlag: woanders wohnen.</p>
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
          <p className="text-gray-600 text-xs text-right mb-4">
            Zuletzt aktualisiert {secondsSince < 10 ? "gerade eben" : `vor ${secondsSince} Sekunden`}
          </p>
        )}
      </div>

      <footer className="text-center py-8 mt-4">
        <p className="text-xs text-gray-700 mb-2 tracking-widest uppercase">PadelYara</p>
        <div className="flex items-center justify-center gap-4">
          <NavLink to="/impressum" className="text-xs text-gray-700 hover:text-gray-400 transition-colors">
            Impressum
          </NavLink>
          <NavLink to="/datenschutz" className="text-xs text-gray-700 hover:text-gray-400 transition-colors">
            Datenschutz
          </NavLink>
        </div>
      </footer>

      {showImprint && <ImprintModal onClose={() => setShowImprint(false)} />}
    </div>
  )
}
