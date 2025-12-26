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
        <div className="max-w-7xl mx-auto px-6 py-12">
            <div className="flex items-center justify-between mb-12">
                <div>
                    <h1 className="text-5xl font-black mb-2 font-display uppercase tracking-tight">Mission Control</h1>
                    <p className="text-xl text-black/60 font-medium">Manage your active travel operations.</p>
                </div>
                <button
                    onClick={onCreateNew}
                    className="neo-btn flex items-center gap-2 bg-retro-green text-black hover:bg-white"
                >
                    <Map className="w-5 h-5" />
                    New Mission
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                {trips.map((trip, idx) => (
                    <motion.div
                        key={trip.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="group relative cursor-pointer"
                        onClick={() => onSelect(trip.id)}
                    >
                        {/* Shadow Block */}
                        <div className="absolute inset-0 bg-black translate-x-2 translate-y-2" />

                        <div className="relative border-2 border-black bg-white p-6 h-full transition-transform hover:-translate-y-1 hover:-translate-x-1 hover:bg-retro-cream">
                            <div className="flex items-start justify-between mb-4">
                                <div className="p-3 bg-retro-blue border-2 border-black text-white">
                                    <Play className="w-6 h-6 fill-current" />
                                </div>
                                <div className="flex flex-col items-end gap-2">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            if (confirm('Are you sure you want to delete this trip?')) {
                                                onDelete(trip.id);
                                            }
                                        }}
                                        className="p-2 text-black hover:bg-retro-pink hover:text-white border-2 border-transparent hover:border-black transition-all"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider border-2 border-black px-2 py-1 bg-white">
                                        <Calendar className="w-3 h-3" />
                                        {new Date(trip.createdAt).toLocaleDateString()}
                                    </div>
                                </div>
                            </div>

                            <h3 className="font-display font-black text-2xl mb-2 leading-none">
                                {trip.title}
                            </h3>

                            <p className="text-sm font-mono text-black/60 mb-8 border-b-2 border-dashed border-black/20 pb-4">
                                "{trip.query || 'No query provided'}"
                            </p>

                            <div className="flex items-center justify-between mt-auto">
                                <span className={`px-3 py-1 text-xs font-bold uppercase tracking-wider border-2 border-black ${trip.status === 'completed'
                                    ? 'bg-retro-green text-black'
                                    : 'bg-retro-yellow text-black'
                                    }`}>
                                    {trip.status}
                                </span>

                                <div className="w-8 h-8 flex items-center justify-center border-2 border-black bg-white group-hover:bg-black group-hover:text-white transition-colors">
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
