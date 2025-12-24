"use client";

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Image from 'next/image';

export const SplashScreen = ({ onComplete }: { onComplete: () => void }) => {
    const [isVisible, setIsVisible] = useState(true);

    useEffect(() => {
        const timer = setTimeout(() => {
            setIsVisible(false);
            setTimeout(onComplete, 800); // Wait for exit animation
        }, 3000); // Show for 3 seconds

        return () => clearTimeout(timer);
    }, [onComplete]);

    return (
        <AnimatePresence>
            {isVisible && (
                <motion.div
                    initial={{ opacity: 1 }}
                    exit={{ opacity: 0, scale: 1.1, filter: 'blur(20px)' }}
                    transition={{ duration: 0.8, ease: 'easeInOut' }}
                    className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-black"
                >
                    {/* Background Image with Parallax-like scaling */}
                    <motion.div
                        initial={{ scale: 1.0 }}
                        animate={{ scale: 1.1 }}
                        transition={{ duration: 4, ease: 'easeOut' }}
                        className="absolute inset-0"
                    >
                        <Image
                            src="/splash-background.png"
                            alt="Travel Destinations"
                            fill
                            className="object-cover opacity-60"
                            priority
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent" />
                    </motion.div>

                    {/* Text Content */}
                    <div className="relative z-10 text-center text-white space-y-6 max-w-2xl px-6">
                        <motion.h1
                            initial={{ y: 20, opacity: 0 }}
                            animate={{ y: 0, opacity: 1 }}
                            transition={{ delay: 0.5, duration: 0.8 }}
                            className="text-5xl md:text-7xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-br from-white via-white to-white/70"
                        >
                            Plan Your<br />Dream Trip
                        </motion.h1>

                        <motion.p
                            initial={{ y: 20, opacity: 0 }}
                            animate={{ y: 0, opacity: 1 }}
                            transition={{ delay: 1.0, duration: 0.8 }}
                            className="text-xl md:text-2xl text-gray-200 font-light"
                        >
                            AI-Curated Itineraries from TikTok's Best Hidden Gems
                        </motion.p>

                        <motion.div
                            initial={{ scale: 0, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            transition={{ delay: 1.5, type: 'spring', stiffness: 200 }}
                        >
                            <div className="w-16 h-1 mt-8 mx-auto bg-gradient-to-r from-blue-500 to-purple-500 rounded-full" />
                        </motion.div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};
