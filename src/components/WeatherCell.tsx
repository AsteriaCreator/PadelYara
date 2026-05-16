import type { Weather } from "../types"

const ICON_MAP: Record<string, string> = {
  sun: "☀️",
  cloud: "☁️",
  "cloud-rain": "🌧️",
}
interface Props {
  weather: Weather | null
}

export default function WeatherCell({ weather }: Props) {
  if (!weather) return <span className="text-sm text-gray-400">—</span>

  return (
    <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-gray-500">
      <span>{ICON_MAP[weather.icon] ?? "🌡️"}</span>
      <span className="font-medium text-gray-400">{weather.temp}°C</span>
      <span>{weather.desc}</span>
      <span className="text-gray-600">·</span>
      <span className="text-blue-400">{weather.rain_prob}% Regen</span>
    </div>
  )
}
