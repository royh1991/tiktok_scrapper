"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { Input } from '@/components/ui/Input';
import { Plane, Search } from 'lucide-react';

interface SearchHeroProps {
    onSearch: (query: string) => void;
    isSearching?: boolean;
}

export const SearchHero = ({ onSearch, isSearching }: SearchHeroProps) => {
    const [query, setQuery] = React.useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (query.trim()) onSearch(query);
    };

    return (
        <section className="relative w-full max-w-7xl mx-auto px-6 py-20 md:py-32 grid md:grid-cols-2 gap-12 items-center">
            {/* Left Column: Text & Input */}
            <div className="space-y-8 z-10">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                >
                    <span className="inline-block px-4 py-2 border-2 border-black bg-retro-yellow text-black font-bold text-sm mb-6 uppercase tracking-wider box-shadow-neo">
                        ✨ AI-Powered Travel Planner
                    </span>
                    <h2 className="text-6xl md:text-8xl font-black font-display text-black leading-[0.9] tracking-tighter mb-6">
                        WHERE TO<br />NEXT?
                    </h2>
                    <p className="text-xl font-medium text-black/70 mt-6 max-w-md border-l-4 border-black pl-6">
                        Discover trending itineraries, hidden spots, and local favorites directly from TikTok videos.
                    </p>
                </motion.div>

                <motion.form
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2, duration: 0.6 }}
                    onSubmit={handleSubmit}
                    className="flex flex-col sm:flex-row gap-4 max-w-lg"
                >
                    <div className="relative flex-1">
                        <Input
                            placeholder="e.g. 7 day itinerary Tokyo"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            className="neo-input w-full text-lg"
                            icon={<Search className="w-5 h-5 text-black" />}
                        />
                    </div>
                    <button
                        disabled={isSearching}
                        className="neo-btn bg-retro-blue text-white hover:bg-white hover:text-black flex items-center justify-center gap-2"
                    >
                        {isSearching ? <span className="animate-spin">⏳</span> : <Plane className="w-5 h-5" />}
                        <span>Let's Go</span>
                    </button>
                </motion.form>

                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="flex flex-wrap gap-3 text-sm font-bold"
                >
                    <span className="uppercase tracking-wider py-1">Trending:</span>
                    {['Tokyo', 'Amalfi Coast', 'Bali', 'New York', 'Iceland'].map((tag) => (
                        <button
                            key={tag}
                            onClick={() => setQuery(`${tag} itinerary`)}
                            className="bg-white border-2 border-black px-3 py-1 hover:bg-retro-pink hover:text-white transition-colors"
                        >
                            #{tag}
                        </button>
                    ))}
                </motion.div>
            </div>

            {/* Right Column: Retro Graphic */}
            <motion.div
                initial={{ opacity: 0, x: 50, rotate: 5 }}
                animate={{ opacity: 1, x: 0, rotate: 0 }}
                transition={{ duration: 0.8, delay: 0.2 }}
                className="relative h-[400px] md:h-[500px] w-full hidden md:flex items-center justify-center"
            >
                {/* Abstract Retro Shapes Composition */}
                <div className="relative w-full h-full">
                    <div className="absolute top-10 right-10 w-64 h-64 bg-retro-green border-4 border-black rounded-full shadow-[16px_16px_0px_0px_rgba(0,0,0,1)] z-10"></div>
                    <div className="absolute bottom-20 left-10 w-48 h-48 bg-retro-pink border-4 border-black rotate-12 shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] z-20"></div>
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-96 bg-white border-4 border-black -rotate-6 z-30 flex flex-col items-center justify-center p-8 shadow-[20px_20px_0px_0px_rgba(0,0,0,1)]">
                        <div className="w-full h-48 bg-gray-100 border-2 border-black mb-6 relative overflow-hidden">
                            {/* Fake Image Placeholder */}
                            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-retro-yellow via-retro-cream to-retro-cream opacity-50"></div>
                            <div className="absolute bottom-0 w-full h-1/2 bg-retro-blue/20"></div>
                        </div>
                        <h3 className="font-display font-black text-2xl uppercase mb-2 self-start">Travel Mode</h3>
                        <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden border border-black">
                            <div className="w-2/3 h-full bg-retro-green"></div>
                        </div>
                        <div className="mt-4 flex gap-2 self-start">
                            <div className="w-3 h-3 rounded-full bg-red-500 border border-black"></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-500 border border-black"></div>
                            <div className="w-3 h-3 rounded-full bg-green-500 border border-black"></div>
                        </div>
                    </div>
                </div>
            </motion.div>
        </section>
    );
};
