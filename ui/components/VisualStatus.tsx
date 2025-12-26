"use client";

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Download, Sparkles, MapPin, Briefcase, Camera } from 'lucide-react';

interface Props {
    stage: 'searching' | 'downloading' | 'processing';
    latestLog?: string;
}

export const VisualStatus = ({ stage, latestLog }: Props) => {

    // 1. Search Stage: Animated Scout Graphic
    const SearchVisual = () => (
        <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.1 }}
            className="relative w-64 h-64 mx-auto"
        >
            <img
                src="/scout_searching.png"
                alt="Scouting"
                className="w-full h-full object-contain drop-shadow-2xl"
            />
            {/* Overlay Pulse */}
            <motion.div
                animate={{ scale: [1, 1.2, 1], opacity: [0.1, 0.3, 0.1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute inset-0 bg-indigo-500 rounded-full blur-[60px] -z-10"
            />
        </motion.div>
    );

    // 2. Download Stage: Animated Suitcase Packing
    const DownloadVisual = () => (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="relative w-64 h-64 mx-auto flex items-center justify-center"
        >
            <div className="relative">
                <motion.div
                    animate={{ y: [0, -5, 0] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="p-8 bg-amber-100 dark:bg-amber-900/20 rounded-[2.5rem] border-4 border-amber-200 dark:border-amber-800 shadow-xl"
                >
                    <Briefcase className="w-24 h-24 text-amber-600 dark:text-amber-400" />
                </motion.div>

                {/* Floating Icons packing into suitcase */}
                <AnimatePresence>
                    {[1, 2, 3].map((i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, y: -40, x: (i - 2) * 40 }}
                            animate={{
                                opacity: [0, 1, 0],
                                y: [-40, 20],
                                scale: [0.5, 1, 0.5]
                            }}
                            transition={{
                                duration: 1.5,
                                repeat: Infinity,
                                delay: i * 0.4,
                                ease: "circIn"
                            }}
                            className="absolute top-0 left-1/2 -ml-4"
                        >
                            {i === 1 ? <div className="p-2 bg-indigo-500 rounded-lg shadow-lg"><Camera className="w-4 h-4 text-white" /></div> :
                                i === 2 ? <div className="p-2 bg-pink-500 rounded-lg shadow-lg"><MapPin className="w-4 h-4 text-white" /></div> :
                                    <div className="p-2 bg-indigo-400 rounded-lg shadow-lg"><Search className="w-4 h-4 text-white" /></div>}
                        </motion.div>
                    ))}
                </AnimatePresence>
            </div>
        </motion.div>
    );

    // 3. Process Stage: Magic Map Drawing
    const ProcessVisual = () => (
        <motion.div
            initial={{ opacity: 0, rotate: -5 }}
            animate={{ opacity: 1, rotate: 0 }}
            exit={{ opacity: 0, rotate: 5 }}
            className="relative w-64 h-64 mx-auto flex items-center justify-center"
        >
            <div className="relative w-full h-48 bg-slate-100 dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 rounded-2xl shadow-inner overflow-hidden">
                {/* Gridded Background */}
                <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#6366f1_1px,transparent_1px)] [background-size:20px_20px]" />

                {/* Wandering Path */}
                <motion.svg className="absolute inset-0 w-full h-full">
                    <motion.path
                        d="M 20 100 Q 80 20 120 100 T 220 80"
                        fill="none"
                        stroke="#6366f1"
                        strokeWidth="3"
                        strokeDasharray="0 400"
                        animate={{ strokeDashoffset: [0, -400] }}
                        transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                    />
                </motion.svg>

                {/* Populating Pins */}
                <AnimatePresence>
                    <motion.div
                        key="pin-1"
                        initial={{ scale: 0 }}
                        animate={{ scale: [0, 1.2, 1] }}
                        className="absolute top-1/4 left-1/3"
                    >
                        <MapPin className="w-8 h-8 text-indigo-500 fill-indigo-500/20" />
                    </motion.div>
                    <motion.div
                        key="sparkle-1"
                        initial={{ scale: 0 }}
                        animate={{ scale: [0, 1.2, 1] }}
                        transition={{ delay: 1 }}
                        className="absolute bottom-1/4 right-1/4"
                    >
                        <Sparkles className="w-6 h-6 text-amber-500" />
                    </motion.div>
                </AnimatePresence>

                {/* Scanning Light */}
                <motion.div
                    animate={{ x: [-256, 256] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute inset-0 w-1/2 bg-gradient-to-r from-transparent via-indigo-500/10 to-transparent -skew-x-12"
                />
            </div>
        </motion.div>
    );

    return (
        <div className="w-full">
            <AnimatePresence mode="wait">
                {stage === 'searching' && <SearchVisual key="search" />}
                {stage === 'downloading' && <DownloadVisual key="download" />}
                {stage === 'processing' && <ProcessVisual key="process" />}
            </AnimatePresence>

            <div className="mt-8 text-center max-w-md mx-auto">
                <motion.p
                    key={latestLog}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-gray-500 dark:text-gray-400 font-medium italic min-h-[3em]"
                >
                    {latestLog || "Preparing your journey..."}
                </motion.p>
            </div>
        </div>
    );
};
