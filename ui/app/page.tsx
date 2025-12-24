"use client";

import React, { useState, useEffect } from 'react';
import { SplashScreen } from '@/components/SplashScreen';
import { SearchHero } from '@/components/SearchHero';
import { LoadingState } from '@/components/LoadingState';
import { VideoGrid } from '@/components/VideoGrid';
import { NavHeader } from '@/components/NavHeader';
import { FooterInfo } from '@/components/FooterInfo';
import { Toast } from '@/components/Toast';
import { EmptyState } from '@/components/EmptyState';
import { AnimatePresence, motion } from 'framer-motion';

type FlowState = 'splash' | 'idle' | 'searching' | 'downloading' | 'processing' | 'results';

export default function Home() {
  const [state, setState] = useState<FlowState>('splash');
  const [logs, setLogs] = useState<string[]>([]);
  const [videos, setVideos] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Transitions
  const handleSplashComplete = () => setState('idle');

  const handleSearch = async (query: string) => {
    setError(null);
    setState('searching');
    setLogs(['Initializing search agents...', `Targeting: ${query}`]);

    try {
      // 1. Search
      setLogs(prev => [...prev, 'Scanning TikTok for viral content...']);
      const searchRes = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });

      if (!searchRes.ok) {
        const errData = await searchRes.json().catch(() => ({}));
        throw new Error(errData.details || 'Search failed');
      }

      // 2. Download
      setState('downloading');
      setLogs(prev => [...prev, 'Found videos. Starting high-speed download...']);
      const dlRes = await fetch('/api/download', { method: 'POST' });
      if (!dlRes.ok) throw new Error('Download failed');

      // 3. Process
      setState('processing');
      setLogs(prev => [...prev, 'Extracting metadata and transcribing audio...']);
      const procRes = await fetch('/api/process', { method: 'POST' });
      if (!procRes.ok) throw new Error('Processing failed');

      // 4. Fetch Results
      setLogs(prev => [...prev, 'Finalizing itinerary...']);
      const resultsRes = await fetch('/api/results');
      const data = await resultsRes.json();
      setVideos(data.videos || []);

      setState('results');

    } catch (e) {
      console.error(e);
      setError('Something went wrong. Please try again.');
      setState('idle');
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-white relative overflow-hidden font-sans selection:bg-indigo-100 selection:text-indigo-900">

      {state === 'splash' && <SplashScreen onComplete={handleSplashComplete} />}

      <NavHeader />

      <div className="relative z-10 min-h-screen flex flex-col pt-20">
        <AnimatePresence mode="wait">

          {state === 'idle' && (
            <motion.div
              key="idle"
              exit={{ opacity: 0, y: -20 }}
              className="flex-1 flex flex-col justify-center"
            >
              <SearchHero onSearch={handleSearch} />
            </motion.div>
          )}

          {(state === 'searching' || state === 'downloading' || state === 'processing') && (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex flex-col justify-center"
            >
              <LoadingState status={state} logs={logs} />
            </motion.div>
          )}

          {state === 'results' && (
            <motion.div
              key="results"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex-1"
            >
              <div className="max-w-7xl mx-auto py-8">
                <div className="px-6 mb-8 flex items-center justify-between">
                  <h2 className="text-3xl font-bold">Your Itinerary</h2>
                  <button
                    onClick={() => setState('idle')}
                    className="text-indigo-500 hover:underline"
                  >
                    New Search
                  </button>
                </div>

                {videos.length > 0 ? (
                  <VideoGrid videos={videos} onVideoClick={(v) => console.log(v)} />
                ) : (
                  <EmptyState />
                )}
              </div>
            </motion.div>
          )}

        </AnimatePresence>

        <FooterInfo />
      </div>

      <Toast
        isVisible={!!error}
        message={error || ''}
        type="error"
        onClose={() => setError(null)}
      />

      {/* Global Background Texture */}
      {state !== 'splash' && (
        <div className="fixed inset-0 z-0 opacity-[0.03] pointer-events-none bg-[url('/result-bg.png')] bg-repeat" />
      )}
    </main>
  );
}
