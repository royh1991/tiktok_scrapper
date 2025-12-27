"use client";

import React from 'react';
import { motion } from 'framer-motion';
import Image from 'next/image';

export const FlightLoader = () => {
    return (
        <div className="relative w-64 h-64 mx-auto">
            {/* Flight Path Rings */}
            <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                className="absolute inset-0 border-4 border-dashed border-indigo-200 dark:border-indigo-900/30 rounded-full"
            />
            <motion.div
                animate={{ rotate: -360 }}
                transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
                className="absolute inset-4 border-2 border-dashed border-blue-100 dark:border-blue-900/30 rounded-full"
            />

            {/* Plane */}
            <motion.div
                animate={{
                    y: [-10, 10, -10],
                    rotate: [0, 5, 0, -5, 0],
                    scale: [1, 1.05, 1]
                }}
                transition={{
                    duration: 4,
                    repeat: Infinity,
                    ease: "easeInOut"
                }}
                className="absolute inset-0 flex items-center justify-center z-10"
            >
                <div className="relative w-40 h-40">
                    <Image
                        src="/loader-plane.png"
                        alt="Loading..."
                        fill
                        className="object-contain drop-shadow-xl"
                        priority
                    />
                </div>
            </motion.div>

            {/* Clouds */}
            <motion.div
                initial={{ x: -100, opacity: 0 }}
                animate={{ x: 200, opacity: [0, 1, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear", delay: 0.5 }}
                className="absolute top-1/2 left-0 w-12 h-8 bg-white/80 rounded-full blur-md"
            />
            <motion.div
                initial={{ x: -100, opacity: 0 }}
                animate={{ x: 200, opacity: [0, 1, 0] }}
                transition={{ duration: 4, repeat: Infinity, ease: "linear", delay: 1.5 }}
                className="absolute bottom-10 left-0 w-8 h-6 bg-white/60 rounded-full blur-md"
            />
        </div>
    );
};
