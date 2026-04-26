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
    <div className="flex items-center gap-1.5 text-sm text-gray-600">
      <span>{ICON_MAP[weather.icon] ?? "🌡️"}</span>
      <span className="font-medium">{weather.temp}°C</span>
      <span className="text-gray-400">{weather.desc}</span>
      <span className="text-gray-300">·</span>
      <span className="text-blue-400">{weather.rain_prob}%</span>
    </div>
  )
}
