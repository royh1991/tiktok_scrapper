"use client";

import React from 'react';
import { motion } from 'framer-motion';

export const AudioWaveform = () => {
    return (
        <div className="flex items-end gap-0.5 h-4">
            {Array.from({ length: 12 }).map((_, i) => (
                <motion.div
                    key={i}
                    className="w-1 bg-indigo-500 rounded-full"
                    animate={{ height: ['20%', '100%', '20%'] }}
                    transition={{
                        duration: 0.8,
                        repeat: Infinity,
                        ease: "easeInOut",
                        delay: i * 0.1,
                        repeatDelay: Math.random() * 0.5
                    }}
                />
            ))}
        </div>
    );
};
