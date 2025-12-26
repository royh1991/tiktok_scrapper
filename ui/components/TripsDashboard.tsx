"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { Map, Calendar, ArrowRight, Play, Trash2 } from 'lucide-react';

interface Trip {
    id: string;
    title: string;
    query: string;
    status: string;
    createdAt: string;
}

interface Props {
    trips: Trip[];
    onSelect: (tripId: string) => void;
    onDelete: (tripId: string) => void;
    onCreateNew: () => void;
}

export const TripsDashboard: React.FC<Props> = ({ trips, onSelect, onDelete, onCreateNew }) => {
    return (
        <div className="max-w-6xl mx-auto px-6 py-12">
            <div className="flex items-center justify-between mb-10">
                <div>
                    <h1 className="text-4xl font-bold mb-2">My Trip Planner</h1>
                    <p className="text-gray-500 dark:text-gray-400">Manage your AI-generated travel itineraries.</p>
                </div>
                <button
                    onClick={onCreateNew}
                    className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl font-semibold transition-all shadow-lg shadow-indigo-500/20 active:scale-95 flex items-center gap-2"
                >
                    <Map className="w-5 h-5" />
                    Create New Trip
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {trips.map((trip, idx) => (
                    <motion.div
                        key={trip.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="group relative bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-3xl p-6 hover:shadow-2xl hover:shadow-indigo-500/10 transition-all cursor-pointer overflow-hidden"
                        onClick={() => onSelect(trip.id)}
                    >
                        {/* Background Accent */}
                        <div className="absolute top-0 right-0 -mr-8 -mt-8 w-32 h-32 bg-indigo-500/5 rounded-full blur-3xl group-hover:bg-indigo-500/10 transition-colors" />

                        <div className="relative z-10">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-3">
                                    <div className="p-3 bg-indigo-50 dark:bg-indigo-950/30 rounded-2xl text-indigo-600">
                                        <Play className="w-5 h-5" />
                                    </div>
                                    <div className="min-w-0">
                                        <h3 className="font-bold text-xl truncate group-hover:text-indigo-600 transition-colors">
                                            {trip.title}
                                        </h3>
                                        <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                            <Calendar className="w-3 h-3" />
                                            {new Date(trip.createdAt).toLocaleDateString()}
                                        </div>
                                    </div>
                                </div>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (confirm('Are you sure you want to delete this trip?')) {
                                            onDelete(trip.id);
                                        }
                                    }}
                                    className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-all"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>

                            <p className="text-sm text-gray-600 dark:text-gray-300 line-clamp-2 mb-6 min-h-[2.5rem]">
                                "{trip.query || 'No query provided'}"
                            </p>

                            <div className="flex items-center justify-between pt-4 border-t border-gray-50 dark:border-gray-800/50">
                                <span className={`px-2.5 py-1 rounded-full text-[10px] uppercase tracking-wider font-bold ${trip.status === 'completed'
                                    ? 'bg-green-100 text-green-700 dark:bg-green-500/10 dark:text-green-400'
                                    : 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400'
                                    }`}>
                                    {trip.status}
                                </span>

                                <div className="p-2 rounded-xl bg-gray-50 dark:bg-gray-800 group-hover:bg-indigo-600 group-hover:text-white transition-all transform translate-x-4 opacity-0 group-hover:translate-x-0 group-hover:opacity-100">
                                    <ArrowRight className="w-4 h-4" />
                                </div>
                            </div>
                        </div>
                    </motion.div>
                ))}
            </div>
        </div>
    );
};
