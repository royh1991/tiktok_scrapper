"use client";

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, MapPin, Sparkles, FolderOpen, ArrowDown, Check } from 'lucide-react';

interface Props {
    stage: 'searching' | 'downloading' | 'processing';
    latestLog?: string;
}

export const VisualStatus = ({ stage, latestLog }: Props) => {

    // 1. Search Stage: Retro Radar Scan
    const SearchVisual = () => (
        <div className="relative w-64 h-64 mx-auto flex items-center justify-center">
            {/* Outer Circle */}
            <div className="absolute inset-0 border-4 border-black rounded-full bg-white shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]"></div>

            {/* Radar Sweep */}
            <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                className="absolute inset-4 rounded-full overflow-hidden"
            >
                <div className="w-full h-1/2 bg-retro-blue/20 border-b-4 border-black origin-bottom"></div>
            </motion.div>

            {/* Target Blip */}
            <motion.div
                animate={{ scale: [0, 1.5, 0], opacity: [1, 0] }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className="absolute w-full h-full border-2 border-retro-blue rounded-full"
            />

            {/* Center Icon */}
            <div className="relative z-10 p-4 bg-retro-yellow border-4 border-black rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                <Search size={48} strokeWidth={2.5} className="text-black" />
            </div>
        </div>
    );

    // 2. Download Stage: Retro Folder Packing
    const DownloadVisual = () => (
        <div className="relative w-64 h-64 mx-auto flex items-center justify-center">
            {/* File Folder Back */}
            <div className="absolute bottom-10 w-48 h-32 bg-retro-cream border-4 border-black rounded-t-xl z-0 transform -skew-x-6 translate-x-2"></div>
            <div className="absolute bottom-10 w-48 h-32 bg-retro-blue border-4 border-black rounded-xl z-10 flex items-center justify-center shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
                <FolderOpen size={48} className="text-white mb-2" strokeWidth={3} />
            </div>

            {/* Falling Files */}
            <AnimatePresence>
                {[0, 1, 2].map((i) => (
                    <motion.div
                        key={i}
                        initial={{ y: -100, opacity: 0, rotate: -10 }}
                        animate={{
                            y: [-80, 40],
                            opacity: [0, 1, 0],
                            rotate: [-10, 5, 0]
                        }}
                        transition={{
                            duration: 1.5,
                            repeat: Infinity,
                            delay: i * 0.5,
                            ease: "easeInOut"
                        }}
                        className="absolute z-20 top-0"
                    >
                        <div className="w-16 h-20 bg-white border-4 border-black flex items-center justify-center shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                            <ArrowDown size={24} className="text-retro-green" />
                        </div>
                    </motion.div>
                ))}
            </AnimatePresence>
        </div>
    );

    // 3. Process Stage: Flat Map Building
    const ProcessVisual = () => (
        <div className="relative w-64 h-64 mx-auto flex items-center justify-center">
            {/* Map Base */}
            <motion.div
                className="w-56 h-40 bg-retro-cream border-4 border-black rotate-[-3deg] shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] overflow-hidden relative"
            >
                {/* Grid Lines */}
                <div className="absolute inset-0 opacity-10 bg-[linear-gradient(rgba(0,0,0,0.5)_2px,transparent_2px),linear-gradient(90deg,rgba(0,0,0,0.5)_2px,transparent_2px)] bg-[size:20px_20px]"></div>

                {/* Animated Path */}
                <svg className="absolute inset-0 w-full h-full pointer-events-none">
                    <motion.path
                        d="M 20 80 Q 80 20 120 80 T 220 60"
                        fill="none"
                        stroke="#FF6B6B"
                        strokeWidth="5"
                        strokeDasharray="0 400"
                        animate={{ strokeDashoffset: [0, -400] }}
                        transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                        strokeLinecap="round"
                    />
                </svg>

                {/* Dropping Pins */}
                <motion.div
                    key="p1"
                    animate={{ y: [0, -10, 0] }}
                    transition={{ duration: 1, repeat: Infinity }}
                    className="absolute top-8 left-12"
                >
                    <MapPin size={24} className="text-retro-green fill-retro-green text-black stroke-[3px]" />
                </motion.div>
                <motion.div
                    key="p2"
                    animate={{ y: [0, -10, 0] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: 0.5 }}
                    className="absolute top-16 right-12"
                >
                    <Sparkles size={24} className="text-retro-yellow fill-retro-yellow text-black stroke-[3px]" />
                </motion.div>
            </motion.div>

            {/* Floating "Processing" Label */}
            <motion.div
                animate={{ rotate: [3, -3, 3] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute -bottom-4 bg-black text-white px-4 py-1 font-bold border-2 border-white shadow-lg"
            >
                AI WORKING
            </motion.div>
        </div>
    );

    return (
        <div className="w-full font-display">
            <AnimatePresence mode="wait">
                {stage === 'searching' && (
                    <motion.div key="s" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <SearchVisual />
                    </motion.div>
                )}
                {stage === 'downloading' && (
                    <motion.div key="d" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <DownloadVisual />
                    </motion.div>
                )}
                {stage === 'processing' && (
                    <motion.div key="p" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <ProcessVisual />
                    </motion.div>
                )}
            </AnimatePresence>

            <div className="mt-8 text-center max-w-md mx-auto relative group">
                {/* Chat Bubble Style Log */}
                <div className="absolute inset-0 bg-white border-4 border-black translate-x-1 translate-y-1 rounded-xl"></div>
                <motion.div
                    key={latestLog}
                    initial={{ y: 5 }}
                    animate={{ y: 0 }}
                    className="relative bg-retro-yellow border-4 border-black p-4 rounded-xl min-h-[4em] flex items-center justify-center"
                >
                    <p className="text-black font-bold text-lg leading-tight">
                        {latestLog || "Booting up mission..."}
                    </p>
                </motion.div>
            </div>
        </div>
    );
};
