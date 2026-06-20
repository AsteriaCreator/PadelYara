import { NavLink } from "react-router-dom"
import { loadMerkliste } from "../hooks/useMerkliste"
import { MY_SLUG_KEY } from "../hooks/useMyProfile"

const TABS = [
  { to: "/turnierjaeger", label: "TURNIERE", exact: true },
  { to: "/turnierjaeger/meine", label: "MEINE", exact: false },
  { to: "/turnierjaeger/merkliste", label: "MERKLISTE", exact: false },
]

export default function TurnierjagerNav() {
  const merklisteCount = Object.keys(loadMerkliste()).length
  const hasProfile = !!localStorage.getItem(MY_SLUG_KEY)

  return (
    <div className="flex gap-1 mb-6 p-1 rounded-xl" style={{ background: "rgba(255,255,255,0.04)" }}>
      {TABS.map(tab => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.exact}
          className="flex-1 text-center py-2 rounded-lg text-xs font-bold tracking-wider transition-colors relative"
          style={({ isActive }) => ({
            fontFamily: "'Barlow Condensed', sans-serif",
            background: isActive ? "rgba(212,245,60,0.12)" : "transparent",
            color: isActive ? "#d4f53c" : "#6b7280",
          })}
        >
          {tab.label}
          {tab.to === "/turnierjaeger/merkliste" && merklisteCount > 0 && (
            <span
              className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full text-[10px] font-bold flex items-center justify-center"
              style={{ background: "#d4f53c", color: "#080810" }}
            >
              {merklisteCount}
            </span>
          )}
          {tab.to === "/turnierjaeger/meine" && hasProfile && (
            <span
              className="absolute -top-1 -right-1 w-2 h-2 rounded-full"
              style={{ background: "#d4f53c" }}
            />
          )}
        </NavLink>
      ))}
    </div>
  )
}
