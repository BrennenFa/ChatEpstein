'use client';

import { useState, useRef, useEffect } from 'react';
import { Message } from '@/types/chat';
import MessageList from './MessageList';
import InputArea from './InputArea';
import Image from 'next/image';

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const streamText = (fullText: string, messageId: string, sources?: any[], citations?: Record<string, string>) => {
    // Split into words for streaming effect
    const words = fullText.split(' ');
    let currentIndex = 0;

    // Create initial empty message with streaming flag
    const initialMessage: Message = {
      id: messageId,
      role: 'assistant',
      content: '',
      sources,
      citations,
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, initialMessage]);

    // Stream words one by one
    const streamInterval = setInterval(() => {
      if (currentIndex < words.length) {
        currentIndex++;

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === messageId
              ? {
                  ...msg,
                  content: words.slice(0, currentIndex).join(' '),
                  isStreaming: true,
                }
              : msg
          )
        );

        // Scroll as we stream
        scrollToBottom();
      } else {
        // Finished streaming - remove cursor
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === messageId
              ? { ...msg, isStreaming: false }
              : msg
          )
        );
        clearInterval(streamInterval);
        setIsLoading(false);
      }
    }, 30); // 30ms per word - adjust for faster/slower streaming
  };

  const handleSendMessage = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: content }),
      });

      if (!response.ok) throw new Error('Failed to get response');

      const data = await response.json();


      // Use streaming effect instead of instant display
      const messageId = (Date.now() + 1).toString();
      streamText(data.answer, messageId, data.sources, data.citations);

    } catch (error) {
      console.error('Error:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Error processing your request. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-black transition-colors">
      {messages.length === 0 && (
        <div className="flex-1 flex items-center justify-center p-12">
          <div className="text-center space-y-6 max-w-3xl">
            <div className="mb-8">
              <Image
                src="/jeff.webp"
                alt="ChatEpstein Logo"
                width={300}
                height={300}
                className="mx-auto rounded-2xl"
              />
            </div>
            <h2 className="text-4xl font-normal text-gray-900 dark:text-gray-100 tracking-tight">
              Ask About the Documents
            </h2>
            <p className="text-gray-500 dark:text-gray-400 text-lg font-light leading-relaxed">
              Search through the Epstein Files with AI-powered analysis
            </p>
          </div>
        </div>
      )}

      {messages.length > 0 && (
        <div className="flex-1 overflow-y-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
            <MessageList messages={messages} isLoading={isLoading} />
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}

      <InputArea onSendMessage={handleSendMessage} isLoading={isLoading} />
    </div>
  );
}
