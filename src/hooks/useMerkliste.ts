import { useState, useRef } from "react"
import type { Tournament } from "../types"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000"
export const MERKLISTE_KEY = "turnierjager_merkliste"

export function loadMerkliste(): Record<string, Tournament> {
  try { return JSON.parse(localStorage.getItem(MERKLISTE_KEY) ?? "{}") } catch { return {} }
}

export function saveMerkliste(m: Record<string, Tournament>) {
  try { localStorage.setItem(MERKLISTE_KEY, JSON.stringify(m)) } catch { /* ignore */ }
}

export function useMerkliste() {
  const [merkliste, setMerkliste] = useState<Record<string, Tournament>>(loadMerkliste)
  const [copied, setCopied] = useState(false)
  const merklisteLoadedFromUrl = useRef(false)

  function toggleMerkliste(t: Tournament) {
    const key = `${t.source}:${t.source_id}`
    setMerkliste(prev => {
      const next = { ...prev }
      if (next[key]) delete next[key]
      else next[key] = t
      saveMerkliste(next)
      return next
    })
  }

  function clearMerkliste() {
    setMerkliste({})
    saveMerkliste({})
  }

  async function shareMerkliste(items: Tournament[]) {
    const ids = items.map(t => t.source_id)
    let url = "https://www.padelyara.at/turnierjaeger/merkliste"
    try {
      const res = await fetch(`${API_BASE}/api/tournaments/share`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      })
      if (res.ok) {
        const data = await res.json() as { code: string }
        url = `https://www.padelyara.at/turnierjaeger/merkliste?m=${data.code}`
      }
    } catch { /* fall back to base URL */ }
    if (navigator.share) {
      void navigator.share({ text: `Schau dir diese Turniere an: ${url}`, url }).catch(() => {})
    } else {
      void navigator.clipboard.writeText(url).catch(() => {})
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    }
  }

  function loadFromUrl() {
    if (merklisteLoadedFromUrl.current) return
    const params = new URLSearchParams(window.location.search)
    const code = params.get("m")
    if (!code) return
    merklisteLoadedFromUrl.current = true
    const clean = new URL(window.location.href)
    clean.searchParams.delete("m")
    window.history.replaceState(null, "", clean.toString())
    void fetch(`${API_BASE}/api/tournaments/share/${encodeURIComponent(code)}`)
      .then(r => r.ok ? r.json() : null)
      .then((data: { tournaments?: Tournament[] } | null) => {
        const incoming = data?.tournaments ?? []
        if (!incoming.length) return
        setMerkliste(prev => {
          const next = { ...prev }
          for (const t of incoming) next[`${t.source}:${t.source_id}`] = t
          saveMerkliste(next)
          return next
        })
      })
      .catch(() => {})
  }

  return { merkliste, toggleMerkliste, clearMerkliste, shareMerkliste, copied, loadFromUrl }
}
