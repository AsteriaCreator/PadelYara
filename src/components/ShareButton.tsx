import { useState } from "react"
import type { SearchParams } from "../types"

export default function ShareButton({ params }: { params: SearchParams | null }) {
  const [copied, setCopied] = useState(false)

  function buildShareText() {
    if (!params) return ""
    const [year, month, day] = params.date.split("-")
    return `Schau mal, ob du am ${day}.${month}.${year} um ${params.time} Uhr in ${params.location} spielen kannst:`
  }

  function handleShare() {
    const url = window.location.href
    const text = buildShareText()
    if (navigator.share) {
      navigator.share({ text, url }).catch(() => {})
    } else {
      navigator.clipboard.writeText(`${text}\n${url}`).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
  }

  return (
    <button
      onClick={handleShare}
      className="text-xs tracking-wide transition-colors"
      style={{ fontFamily: "'Barlow Condensed', sans-serif", color: copied ? "#d4f53c" : "rgba(212,245,60,0.4)" }}
    >
      {copied ? "KOPIERT" : "TEILEN"}
    </button>
  )
}
