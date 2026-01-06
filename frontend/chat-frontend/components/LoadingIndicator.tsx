export default function LoadingIndicator() {
  return (
    <div className="flex justify-start mb-6">
      <div className="bg-zinc-800 text-white border border-zinc-700 rounded-2xl p-5">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            <div className="w-2 h-2 bg-white rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 bg-white rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 bg-white rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-sm text-zinc-400">Searching documents...</span>
        </div>
      </div>
    </div>
  );
}
