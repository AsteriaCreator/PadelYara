export default function SkeletonRow() {
  return (
    <div className="px-4 py-3 border-b border-gray-700/50 last:border-0 animate-pulse">
      <div className="flex items-center justify-between mb-2">
        <div className="h-4 bg-gray-700 rounded w-44" />
        <div className="h-5 bg-gray-700 rounded-full w-20 ml-3 shrink-0" />
      </div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-3 bg-gray-800 rounded w-16" />
          <div className="h-3 bg-gray-800 rounded w-1" />
          <div className="h-3 bg-gray-800 rounded w-14" />
          <div className="h-3 bg-gray-800 rounded w-1" />
          <div className="h-3 bg-gray-800 rounded w-20" />
        </div>
        <div className="h-6 bg-gray-700 rounded w-24 ml-3 shrink-0" />
      </div>
    </div>
  )
}
