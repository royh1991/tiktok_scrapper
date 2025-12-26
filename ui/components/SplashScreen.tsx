"use client";

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

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
                    exit={{ y: -1000, opacity: 1 }}
                    transition={{ duration: 0.8, ease: [0.76, 0, 0.24, 1] }} // smooth swipe up
                    className="fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden bg-retro-green"
                >
                    <div className="relative z-10 text-center space-y-8 px-6">
                        <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            transition={{ delay: 0.2, duration: 0.8 }}
                            className="bg-white border-4 border-black p-8 shadow-[16px_16px_0px_0px_rgba(0,0,0,1)]"
                        >
                            <h1 className="text-6xl md:text-9xl font-black tracking-tighter font-display text-black mb-2">
                                PLAN<br />IT.
                            </h1>
                            <p className="text-xl md:text-3xl font-bold font-mono tracking-tight text-black border-t-4 border-black pt-4">
                                AI VACATION PLANNER
                            </p>
                        </motion.div>

                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 1 }}
                            className="flex items-center justify-center gap-2"
                        >
                            <div className="w-4 h-4 bg-black animate-bounce delay-0"></div>
                            <div className="w-4 h-4 bg-black animate-bounce delay-100"></div>
                            <div className="w-4 h-4 bg-black animate-bounce delay-200"></div>
                        </motion.div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};
