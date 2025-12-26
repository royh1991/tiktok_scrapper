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
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/40 backdrop-blur-sm">
            <motion.div
                initial={{ opacity: 0, scale: 0.9, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.9, y: 20 }}
                className="relative w-full max-w-lg bg-white dark:bg-gray-900 rounded-[2.5rem] shadow-2xl overflow-hidden"
            >
                <button
                    onClick={onClose}
                    className="absolute top-6 right-6 p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors"
                >
                    <X className="w-5 h-5" />
                </button>

                <div className="px-10 pt-10 pb-12">
                    <div className="mb-8">
                        <h2 className="text-3xl font-bold mb-2">Plan a New Trip</h2>
                        <p className="text-gray-500 dark:text-gray-400">Where are we going?</p>
                    </div>

                    <form onSubmit={(e) => { e.preventDefault(); onSubmit(title, query); }} className="space-y-6">
                        <div>
                            <label className="block text-sm font-semibold mb-2 ml-1 text-gray-700 dark:text-gray-300">
                                Trip Name
                            </label>
                            <div className="relative">
                                <Map className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                                <input
                                    type="text"
                                    placeholder="e.g. 7 Days in Tokyo"
                                    value={title}
                                    onChange={(e) => setTitle(e.target.value)}
                                    className="w-full pl-12 pr-6 py-4 bg-gray-50 dark:bg-gray-800 border-none rounded-2xl focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
                                    required
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-semibold mb-2 ml-1 text-gray-700 dark:text-gray-300">
                                Search Query
                            </label>
                            <div className="relative">
                                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                                <input
                                    type="text"
                                    placeholder="e.g. tokyo travel tips 2024"
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                    className="w-full pl-12 pr-6 py-4 bg-gray-50 dark:bg-gray-800 border-none rounded-2xl focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
                                    required
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            className="w-full py-5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl font-bold text-lg transition-all shadow-xl shadow-indigo-500/25 active:scale-[0.98] mt-4"
                        >
                            Start Planning
                        </button>
                    </form>
                </div>
            </motion.div>
        </div>
    );
};
