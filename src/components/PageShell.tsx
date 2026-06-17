import React from "react"
import Nav from "./Nav"
import { BG_STYLE } from "../styles"

export default function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen overflow-x-hidden" style={BG_STYLE}>
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="mb-6">
          <img src="/lockup-horizontal-dark.svg" alt="PadelYara" className="h-24 w-auto block" />
        </div>
        <Nav />
        {children}
      </div>
    </div>
  )
}
