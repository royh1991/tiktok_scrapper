"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { Trip, Query } from '@/types'; // Need to define types
import { Plus, ArrowRight, Play, ShoppingBag, MapPin, Coffee } from 'lucide-react';

interface TripDetailsProps {
    trip: any; // Using any for now, will refine
    queries: any[];
    onSelectQuery: (queryId: string) => void;
    onAddQuery: () => void;
    onBack: () => void;
}

export const TripDetails: React.FC<TripDetailsProps> = ({ trip, queries, onSelectQuery, onAddQuery, onBack }) => {
    return (
        <div className="w-full max-w-7xl mx-auto py-12 px-6">
            <div className="flex items-center justify-between mb-12">
                <div>
                    <button 
                        onClick={onBack}
                        className="text-sm font-bold uppercase tracking-wider text-black/50 hover:text-black mb-2 transition-colors"
                    >
                        ← Back to Trips
                    </button>
                    <h1 className="text-5xl md:text-7xl font-black font-display uppercase tracking-tighter">
                        {trip.title}
                    </h1>
                    <p className="text-xl font-medium text-black/60 mt-2">
                        {queries.length} active missions
                    </p>
                </div>
                <button
                    onClick={onAddQuery}
                    className="neo-btn bg-retro-green flex items-center gap-2"
                >
                    <Plus className="w-5 h-5" />
                    <span>New Mission</span>
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {queries.map((query, idx) => (
                    <motion.div
                        key={query.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="neo-card p-6 group cursor-pointer hover:bg-yellow-50 transition-colors"
                        onClick={() => onSelectQuery(query.id)}
                    >
                        <div className="flex justify-between items-start mb-4">
                            <div className="w-12 h-12 bg-retro-blue border-2 border-black flex items-center justify-center text-white font-bold text-xl">
                                {idx + 1}
                            </div>
                            <div className="px-3 py-1 bg-black text-white text-xs font-bold uppercase tracking-wider">
                                {query.status || 'Active'}
                            </div>
                        </div>
                        
                        <h3 className="text-2xl font-black font-display uppercase leading-none mb-2 group-hover:underline">
                            {query.query}
                        </h3>
                        <p className="text-sm text-black/60 font-medium mb-6">
                            Created {new Date(query.createdAt).toLocaleDateString()}
                        </p>

                        <div className="flex justify-end">
                            <span className="w-10 h-10 border-2 border-black bg-white flex items-center justify-center group-hover:bg-black group-hover:text-white transition-all">
                                <ArrowRight className="w-5 h-5" />
                            </span>
                        </div>
                    </motion.div>
                ))}

                {/* Empty State / Call to Action */}
                {queries.length === 0 && (
                    <div className="col-span-full py-20 text-center border-4 border-dashed border-black/10 rounded-lg">
                        <h3 className="text-2xl font-bold text-black/40 mb-4 font-display uppercase">No missions yet</h3>
                        <button
                            onClick={onAddQuery}
                            className="bg-black text-white px-6 py-2 list-none font-bold uppercase hover:bg-retro-blue transition-colors"
                        >
                            Start your first search
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};
