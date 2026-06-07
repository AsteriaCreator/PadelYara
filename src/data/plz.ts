// Austrian postal-code → Bundesland mapping. Derived from the PLZ first digit
// (with the Tirol/Vorarlberg split inside the 6xxx range), because the venue
// `region` field is empty on most records and can't drive a clean state filter.
// Used by the Padelrevier map to filter pins by Bundesland and to deep-link into
// the Court Finder by the venue's PLZ.

const FIRST_DIGIT_BL: Record<string, string> = {
  "1": "Wien",
  "2": "Niederösterreich",
  "3": "Niederösterreich",
  "4": "Oberösterreich",
  "5": "Salzburg",
  "7": "Burgenland",
  "8": "Steiermark",
  "9": "Kärnten",
}

/** Extract the 4-digit Austrian postal code from a free-form address string. */
export function plzFromAddress(address: string): string | null {
  const m = address.match(/\b(\d{4})\b/)
  return m ? m[1] : null
}

/** Map an address to its Austrian Bundesland via its postal code. */
export function bundeslandFromAddress(address: string): string {
  const plz = plzFromAddress(address)
  if (!plz) return "Unbekannt"
  // 6xxx splits: Vorarlberg = 68xx–69xx, the rest of 6xxx is Tirol.
  if (plz[0] === "6") {
    return plz.startsWith("68") || plz.startsWith("69") ? "Vorarlberg" : "Tirol"
  }
  return FIRST_DIGIT_BL[plz[0]] ?? "Unbekannt"
}
