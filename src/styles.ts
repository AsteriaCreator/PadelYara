import type React from "react"

export const BG_STYLE: React.CSSProperties = {
  backgroundColor: "#080810",
  backgroundImage: `
    radial-gradient(ellipse 80% 40% at 50% 0%, rgba(212,245,60,0.18) 0%, transparent 70%),
    repeating-linear-gradient(45deg, rgba(212,245,60,0.12) 0px 1px, transparent 1px 14px),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E")
  `,
  backgroundSize: "auto, auto, 200px 200px",
}
