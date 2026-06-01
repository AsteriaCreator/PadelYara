import type { Weather, CourtType } from "../types"

const ICON_MAP: Record<string, string> = {
  sun: "☀️",
  cloud: "☁️",
  "cloud-rain": "🌧️",
}

function getWeatherHint(rain_prob: number, searchCourtType: CourtType): string | null {
  if (searchCourtType === "indoor") return null

  if (searchCourtType === "outdoor") {
    if (rain_prob <= 20) return "Bedingungen gut"
    if (rain_prob <= 40) return "Regen möglich"
    if (rain_prob <= 65) return "Regen wahrscheinlich"
    return "Schlechte Bedingungen"
  }

  // both
  if (rain_prob <= 20) return "Outdoor gut möglich"
  if (rain_prob <= 40) return "Regen möglich — eher Indoor buchen"
  if (rain_prob <= 65) return "Regen wahrscheinlich — Indoor empfohlen"
  return "Regen erwartet — Indoor empfohlen"
}

function getHintColor(rain_prob: number): string {
  if (rain_prob <= 20) return "text-green-400"
  if (rain_prob <= 40) return "text-amber-400"
  return "text-red-400"
}

interface Props {
  weather: Weather | null
  searchCourtType: CourtType
}

export default function WeatherCell({ weather, searchCourtType }: Props) {
  if (!weather) return <span className="text-sm text-gray-400">—</span>

  const hint = getWeatherHint(weather.rain_prob, searchCourtType)

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex flex-wrap items-center gap-x-1.5 text-xs text-gray-500">
        <span>{ICON_MAP[weather.icon] ?? "🌡️"}</span>
        <span className="font-medium text-gray-400">{weather.temp}°C</span>
        <span>{weather.desc}</span>
        <span className="text-gray-600">·</span>
        <span className="text-blue-400">{weather.rain_prob}% Regen</span>
      </div>
      {hint && (
        <span className={`text-xs font-medium ${getHintColor(weather.rain_prob)}`}>
          {hint}
        </span>
      )}
    </div>
  )
}
