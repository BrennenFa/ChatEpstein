'use client';

import ChatInterface from '@/components/ChatInterface';
import Header from '@/components/Header';

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-white dark:bg-black transition-colors">
      <Header />
      <main className="flex-1 flex flex-col max-w-6xl w-full mx-auto px-8 py-6">
        <ChatInterface />
      </main>
    </div>
  );
}
