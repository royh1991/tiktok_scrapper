"use client";

import React from 'react';
import { motion } from 'framer-motion';
import Image from 'next/image';
import { TripInput } from '@/components/ui/Input'; // Assuming Input export alias allows this or I usually export as Input
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
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
        <section className="relative w-full max-w-6xl mx-auto px-4 py-12 md:py-24 grid md:grid-cols-2 gap-12 items-center">
            {/* Left Column: Text & Input */}
            <div className="space-y-8 z-10">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                >
                    <span className="inline-block px-4 py-2 rounded-full bg-blue-100 text-blue-600 font-semibold text-sm mb-4">
                        ✨ AI-Powered Travel Planner
                    </span>
                    <h2 className="text-5xl md:text-6xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-400">
                        Where to next?
                    </h2>
                    <p className="text-xl text-gray-500 dark:text-gray-400 mt-4 max-w-md">
                        Discover trending itineraries, hidden spots, and local favorites directly from TikTok videos.
                    </p>
                </motion.div>

                <motion.form
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2, duration: 0.6 }}
                    onSubmit={handleSubmit}
                    className="flex flex-col sm:flex-row gap-4"
                >
                    <Input
                        placeholder="e.g. 7 day itinerary Tokyo"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="flex-1 shadow-lg border-transparent focus:border-indigo-500"
                        icon={<Search className="w-5 h-5 text-indigo-500" />}
                    />
                    <Button
                        disabled={isSearching}
                        size="lg"
                        className="shadow-xl shadow-indigo-500/20"
                        icon={isSearching ? <span className="animate-spin">⏳</span> : <Plane className="w-5 h-5" />}
                    >
                        {isSearching ? 'Planning...' : 'Let\'s Go'}
                    </Button>
                </motion.form>

                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="flex flex-wrap gap-2 text-sm text-gray-500"
                >
                    <span className="font-medium">Trending:</span>
                    {['Tokyo', 'Amalfi Coast', 'Bali', 'New York', 'Iceland'].map((tag) => (
                        <button
                            key={tag}
                            onClick={() => setQuery(`${tag} itinerary`)}
                            className="hover:text-indigo-600 hover:underline transition-colors"
                        >
                            #{tag}
                        </button>
                    ))}
                </motion.div>
            </div>

            {/* Right Column: 3D Composition */}
            <motion.div
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.8, delay: 0.2 }}
                className="relative h-[400px] md:h-[600px] w-full"
            >
                <Image
                    src="/search-hero.png"
                    alt="Travel Inspiration"
                    fill
                    className="object-contain drop-shadow-2xl"
                    priority
                />

                {/* Floating Elements Animation */}
                <motion.div
                    animate={{ y: [0, -20, 0] }}
                    transition={{ repeat: Infinity, duration: 5, ease: "easeInOut" }}
                    className="absolute top-10 right-10 bg-white dark:bg-gray-800 p-4 rounded-2xl shadow-xl max-w-[150px]"
                >
                    <div className="flex items-center gap-2 mb-2">
                        <div className="w-3 h-3 rounded-full bg-green-500" />
                        <span className="text-xs font-bold">Live Search</span>
                    </div>
                    <p className="text-xs text-gray-500">Scanning 50+ TikToks...</p>
                </motion.div>
            </motion.div>
        </section>
    );
};
