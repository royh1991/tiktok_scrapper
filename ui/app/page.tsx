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
import { TripDetails } from '@/components/TripDetails';

type FlowState = 'splash' | 'idle' | 'view-trip' | 'searching' | 'downloading' | 'processing' | 'results';

export default function Home() {
  const [state, setState] = useState<FlowState>('splash');
  const [logs, setLogs] = useState<string[]>([]);
  const [videos, setVideos] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [trips, setTrips] = useState<any[]>([]);
  const [activeTripId, setActiveTripId] = useState<string | null>(null);
  const [activeTrip, setActiveTrip] = useState<any>(null);
  const [queries, setQueries] = useState<any[]>([]);
  const [activeQueryId, setActiveQueryId] = useState<string | null>(null);
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
    const trip = trips.find(t => t.id === tripId);
    setActiveTrip(trip);

    try {
      const res = await fetch(`/api/queries?tripId=${tripId}`);
      const data = await res.json();
      setQueries(data.queries || []);
      setState('view-trip');
    } catch (e) {
      console.error("Failed to load queries", e);
      setError('Failed to load trip details');
    }
  };

  const handleSelectQuery = async (queryId: string) => {
    setActiveQueryId(queryId);
    setState('results');
    try {
      // Updated to pass queryId
      const resultsRes = await fetch(`/api/results?tripId=${activeTripId}&queryId=${queryId}`);
      const data = await resultsRes.json();
      setVideos(data.videos || []);
    } catch (e) {
      setError('Failed to load query results');
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

      // 0.5 Create Query
      const queryRes = await fetch('/api/queries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tripId, query })
      });
      const queryData = await queryRes.json();
      if (!queryRes.ok) throw new Error(queryData.error || 'Failed to create query');

      const queryId = queryData.queryId;

      // 1. Search (Streaming)
      await streamResponse('/api/search', { query, tripId, queryId }, (line) => {
        setLogs(prev => [...prev.slice(-100), line]);
      });

      // 2. Download (Streaming)
      setState('downloading');
      setLogs([]); // Clear logs to trigger "startup" animation for this phase
      await streamResponse('/api/download', { tripId, queryId }, (line) => {
        setLogs(prev => [...prev.slice(-100), line]);
      });

      // 3. Process (Streaming)
      setState('processing');
      setLogs([]); // Clear logs again for processing phase
      await streamResponse('/api/process', { tripId, queryId }, (line) => {
        setLogs(prev => [...prev.slice(-100), line]);
      });

      // 4. Fetch Results
      setLogs(prev => [...prev, 'Finalizing itinerary...']);
      const resultsRes = await fetch(`/api/results?tripId=${tripId}&queryId=${queryId}`);
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

          {state === 'view-trip' && activeTrip && (
            <motion.div
              key="view-trip"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="flex-1"
            >
              <TripDetails
                trip={activeTrip}
                queries={queries}
                onSelectQuery={handleSelectQuery}
                onAddQuery={() => setIsTripFormOpen(true)}
                onBack={() => setState('idle')}
              />
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
