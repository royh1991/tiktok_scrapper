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
import { TripsDashboard } from '@/components/TripsDashboard';
import { TripForm } from '@/components/TripForm';
import { AnimatePresence, motion } from 'framer-motion';

type FlowState = 'splash' | 'idle' | 'searching' | 'downloading' | 'processing' | 'results';

export default function Home() {
  const [state, setState] = useState<FlowState>('splash');
  const [logs, setLogs] = useState<string[]>([]);
  const [videos, setVideos] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [trips, setTrips] = useState<any[]>([]);
  const [activeTripId, setActiveTripId] = useState<string | null>(null);
  const [isTripFormOpen, setIsTripFormOpen] = useState(false);

  // Transitions
  const handleSplashComplete = () => setState('idle');

  useEffect(() => {
    fetchTrips();
  }, []);

  const fetchTrips = async () => {
    try {
      const res = await fetch('/api/trips');
      const data = await res.json();
      setTrips(data.trips || []);
    } catch (e) {
      console.error('Failed to fetch trips', e);
    }
  };

  const handleSelectTrip = async (tripId: string) => {
    setActiveTripId(tripId);
    setState('results');
    try {
      const resultsRes = await fetch(`/api/results?tripId=${tripId}`);
      const data = await resultsRes.json();
      setVideos(data.videos || []);
    } catch (e) {
      setError('Failed to load trip results');
    }
  };

  const handleDeleteTrip = async (tripId: string) => {
    try {
      const res = await fetch(`/api/trips/delete?tripId=${tripId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete trip');
      fetchTrips();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleCreateTrip = async (title: string, query: string) => {
    setIsTripFormOpen(false);
    setError(null);
    setState('searching');
    setLogs(['Initializing search agents...', `Creating trip: ${title}`]);

    const streamResponse = async (url: string, body: any, onChunk: (text: string) => void) => {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.error || 'Request failed');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error('No reader available');

      let accumulated = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        accumulated += decoder.decode(value, { stream: true });
        const lines = accumulated.split('\n');
        accumulated = lines.pop() || '';
        for (const line of lines) {
          if (line.trim()) onChunk(line);
        }
      }
      if (accumulated.trim()) onChunk(accumulated);
    };

    try {
      // 0. Create Trip
      const tripRes = await fetch('/api/trips', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, query })
      });
      const tripData = await tripRes.json();
      if (!tripRes.ok) throw new Error(tripData.error || 'Failed to create trip');

      const tripId = tripData.tripId;
      setActiveTripId(tripId);

      // 1. Search (Streaming)
      await streamResponse('/api/search', { query, tripId }, (line) => {
        setLogs(prev => [...prev.slice(-100), line]);
      });

      // 2. Download (Streaming)
      setState('downloading');
      setLogs([]); // Clear logs to trigger "startup" animation for this phase
      await streamResponse('/api/download', { tripId }, (line) => {
        setLogs(prev => [...prev.slice(-100), line]);
      });

      // 3. Process (Streaming)
      setState('processing');
      setLogs([]); // Clear logs again for processing phase
      await streamResponse('/api/process', { tripId }, (line) => {
        setLogs(prev => [...prev.slice(-100), line]);
      });

      // 4. Fetch Results
      setLogs(prev => [...prev, 'Finalizing itinerary...']);
      const resultsRes = await fetch(`/api/results?tripId=${tripId}`);
      const data = await resultsRes.json();
      setVideos(data.videos || []);

      setState('results');
      fetchTrips();

    } catch (e: any) {
      console.error(e);
      setError(e.message || 'Something went wrong. Please try again.');
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
              className="flex-1 flex flex-col"
            >
              {trips.length > 0 ? (
                <TripsDashboard
                  trips={trips}
                  onSelect={handleSelectTrip}
                  onDelete={handleDeleteTrip}
                  onCreateNew={() => setIsTripFormOpen(true)}
                />
              ) : (
                <div className="flex-1 flex flex-col justify-center">
                  <SearchHero onSearch={() => setIsTripFormOpen(true)} />
                </div>
              )}
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
                    Back to Dashboard
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

      <TripForm
        isOpen={isTripFormOpen}
        onClose={() => setIsTripFormOpen(false)}
        onSubmit={handleCreateTrip}
      />

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
