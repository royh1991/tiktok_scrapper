"use client";

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Map, Search } from 'lucide-react';

interface Props {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (title: string, query: string) => void;
}

export const TripForm: React.FC<Props> = ({ isOpen, onClose, onSubmit }) => {
    const [title, setTitle] = useState('');
    const [query, setQuery] = useState('');

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-retro-cream/80 backdrop-blur-sm">
            <motion.div
                initial={{ opacity: 0, scale: 0.9, rotate: -2 }}
                animate={{ opacity: 1, scale: 1, rotate: 0 }}
                exit={{ opacity: 0, scale: 0.9, rotate: 2 }}
                className="relative w-full max-w-lg bg-white border-2 border-black shadow-[var(--shadow-neo-lg)] p-0 overflow-hidden"
            >
                {/* Header Strip */}
                <div className="bg-retro-yellow border-b-2 border-black p-4 flex justify-between items-center">
                    <h2 className="text-xl font-black font-display uppercase tracking-tight">New Mission</h2>
                    <button
                        onClick={onClose}
                        className="p-1 hover:bg-white border-2 border-transparent hover:border-black transition-all"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-8">
                    <div className="mb-8">
                        <h2 className="text-3xl font-black mb-2 leading-none font-display">Plan a New Trip</h2>
                        <p className="text-black/60 font-medium">Where are we going today?</p>
                    </div>

                    <form onSubmit={(e) => { e.preventDefault(); onSubmit(title, query); }} className="space-y-6">
                        <div>
                            <label className="block text-xs font-bold uppercase tracking-wider mb-2 ml-1">
                                Trip Name
                            </label>
                            <div className="relative">
                                <div className="absolute left-4 top-1/2 -translate-y-1/2 w-8 h-8 bg-black flex items-center justify-center text-white border-2 border-black">
                                    <Map className="w-4 h-4" />
                                </div>
                                <input
                                    type="text"
                                    placeholder="e.g. 7 Days in Tokyo"
                                    value={title}
                                    onChange={(e) => setTitle(e.target.value)}
                                    className="neo-input w-full pl-16"
                                    required
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-xs font-bold uppercase tracking-wider mb-2 ml-1">
                                Search Query
                            </label>
                            <div className="relative">
                                <div className="absolute left-4 top-1/2 -translate-y-1/2 w-8 h-8 bg-retro-blue flex items-center justify-center text-white border-2 border-black">
                                    <Search className="w-4 h-4" />
                                </div>
                                <input
                                    type="text"
                                    placeholder="e.g. tokyo travel tips 2024"
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                    className="neo-input w-full pl-16"
                                    required
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            className="neo-btn w-full bg-retro-green flex justify-center items-center gap-2 mt-8 text-lg"
                        >
                            Start Planning
                        </button>
                    </form>
                </div>
            </motion.div>
        </div>
    );
};
