import { Source } from '@/types/chat';

interface CitationCardProps {
  source: Source;
  index: number;
}

export default function CitationCard({ source, index }: CitationCardProps) {
  return (
    <div className="bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl p-4 hover:shadow-md transition-all">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-6 h-6 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-full flex items-center justify-center text-xs font-medium">
          {index}
        </div>
        <div className="flex-1">
          <div className="flex gap-2 mb-2">
            <span className="text-xs font-mono bg-gray-100 dark:bg-zinc-800 text-gray-700 dark:text-gray-300 px-2 py-1 rounded-md">
              {source.documentId}
            </span>
            <span className="text-xs text-gray-500 dark:text-gray-400 font-light">
              Page {source.pageNumber}
            </span>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 italic font-light leading-relaxed">
            &quot;{source.quote}&quot;
          </p>
        </div>
      </div>
    </div>
  );
}
