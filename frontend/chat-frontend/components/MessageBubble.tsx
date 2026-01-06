import React from 'react';
import { Message } from '@/types/chat';
import CitationCard from './CitationCard';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  // Preprocess content to convert citations into markdown links
  const preprocessContent = (text: string): string => {
    if (!message.citations || Object.keys(message.citations).length === 0) {
      console.log('No citations found in message');
      return text;
    }

    // Regex pattern to match citations: (DOJ-OGR-00024943, Page 1.0) or (dataset8_EFTA00017819, Page 1.0)
    const citationPattern = /\(([A-Za-z0-9\-_]+),\s*Page\s+([^\)]+)\)/g;

    const processed = text.replace(citationPattern, (fullMatch, docId, page) => {
      const citationKey = `${docId}, Page ${page}`;
      const url = message.citations![citationKey];


      if (url && url !== "N/A") {
        // Convert to markdown link: [text](url)
        return `[${fullMatch}](${url})`;
      }
      return fullMatch;
    });

    return processed;
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-8`}>
      <div className={`max-w-3xl ${isUser ? '' : 'w-full'}`}>
        <div
          className={`rounded-2xl px-6 py-4 transition-all ${
            isUser
              ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-md'
              : 'bg-gray-50 dark:bg-zinc-900 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-zinc-800'
          }`}
        >
          <div className="prose prose-lg max-w-none">
            {isUser ? (
              // User messages: plain text
              <div className="whitespace-pre-wrap text-white font-normal leading-relaxed">{message.content}</div>
            ) : (
              // Assistant messages: render markdown with links
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ node, ...props }) => (
                    <a
                      {...props}
                      className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 underline transition-colors"
                      target="_blank"
                      rel="noopener noreferrer"
                    />
                  ),
                  p: ({ node, ...props }) => (
                    <p {...props} className="mb-4 last:mb-0 text-gray-900 dark:text-gray-100 font-normal leading-relaxed" />
                  ),
                  strong: ({ node, ...props }) => (
                    <strong {...props} className="font-semibold text-gray-900 dark:text-gray-100" />
                  ),
                  ul: ({ node, ...props }) => (
                    <ul {...props} className="list-disc pl-6 mb-4 space-y-2 text-gray-900 dark:text-gray-100" />
                  ),
                  ol: ({ node, ...props }) => (
                    <ol {...props} className="list-decimal pl-6 mb-4 space-y-2 text-gray-900 dark:text-gray-100" />
                  ),
                }}
              >
                {preprocessContent(message.content)}
              </ReactMarkdown>
            )}
            {message.isStreaming && (
              <span className="inline-block w-1.5 h-5 ml-1 bg-gray-900 dark:bg-gray-100 animate-pulse rounded-sm" />
            )}
          </div>
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-4 space-y-3">
            {message.sources.map((source, idx) => (
              <CitationCard key={idx} source={source} index={idx + 1} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
