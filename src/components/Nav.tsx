import { NavLink } from "react-router-dom"

const NAV_LINK_STYLE = ({ isActive }: { isActive: boolean }) => ({
  display: "inline-block",
  paddingBottom: "8px",
  fontSize: "1rem",
  fontWeight: 600,
  marginRight: "24px",
  color: isActive ? "#ffffff" : "#4b5563",
  borderBottom: isActive ? "2px solid #d4f53c" : "2px solid transparent",
  textDecoration: "none",
  transition: "color 0.15s",
})

export default function Nav() {
  return (
    <div className="mb-2 border-b border-gray-800">
      <NavLink to="/" end style={NAV_LINK_STYLE}>Court Finder</NavLink>
      <NavLink to="/padelrevier" style={NAV_LINK_STYLE}>Padelrevier</NavLink>
      <NavLink to="/turnierjaeger" style={NAV_LINK_STYLE}>Turnierjagd</NavLink>
      <NavLink to="/about" style={NAV_LINK_STYLE}>Über Yara</NavLink>
    </div>
  )
}
