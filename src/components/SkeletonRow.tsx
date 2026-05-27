export default function SkeletonRow() {
  return (
    <div className="px-4 py-3 border-b border-gray-700/50 last:border-0 animate-pulse">
      <div className="flex items-center justify-between mb-2 min-w-0">
        {/* min-w-0 lets the name bar shrink/truncate rather than overflow */}
        <div className="h-4 bg-gray-700 rounded w-44 min-w-0 shrink" />
        <div className="h-5 bg-gray-700 rounded-full w-20 ml-3 shrink-0" />
      </div>
      <div className="flex items-center justify-between">
        {/* flex-1 min-w-0 overflow-hidden: the bar row takes remaining space
            and clips instead of pushing the button off-screen on narrow viewports */}
        <div className="flex items-center gap-2 flex-1 min-w-0 overflow-hidden">
          <div className="h-3 bg-gray-800 rounded w-12 shrink-0" />
          <div className="h-3 bg-gray-800 rounded w-1 shrink-0" />
          <div className="h-3 bg-gray-800 rounded w-10 shrink-0" />
          <div className="h-3 bg-gray-800 rounded w-1 shrink-0" />
          <div className="h-3 bg-gray-800 rounded w-16 shrink-0" />
        </div>
        <div className="h-6 bg-gray-700 rounded w-24 ml-3 shrink-0" />
      </div>
    </div>
  )
}
