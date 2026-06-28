import { NavLink } from "react-router-dom"

const SOCIALS = [
  { href: "https://www.instagram.com/padelyara", label: "Instagram", path: "M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" },
  { href: "https://www.facebook.com/padelyara", label: "Facebook", path: "M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" },
]

export default function Footer() {
  return (
    <footer className="text-center py-8 mt-4">
      {/* Partnerships */}
      <div className="mb-8">
        <p className="text-gray-500 text-sm mb-1">Anlage, Marke oder Verband?</p>
        <p className="text-gray-600 text-xs mb-3">Wenn wir zusammenpassen, sollten wir reden.</p>
        <a
          href="mailto:yara@adventure-it.at?subject=Partnerschaft%20mit%20PadelYara"
          className="inline-block text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors"
          style={{
            border: "1px solid rgba(212,245,60,0.3)",
            color: "rgba(212,245,60,0.8)",
            fontFamily: "'Barlow Condensed', sans-serif",
            letterSpacing: "0.05em",
          }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = "rgba(212,245,60,0.7)")}
          onMouseLeave={e => (e.currentTarget.style.borderColor = "rgba(212,245,60,0.3)")}
        >
          PARTNER WERDEN
        </a>
      </div>

      <p className="text-xs text-gray-500 mb-2 tracking-widest uppercase">PadelYara</p>
      <div className="flex items-center justify-center gap-3 mb-3">
        {SOCIALS.map(({ href, label, path }) => (
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
  )
}
