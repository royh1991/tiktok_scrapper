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
                            className="bg-white border-4 border-black p-8 shadow-[16px_16px_0px_0px_rgba(0,0,0,1)] relative"
                        >
                            <h1 className="text-6xl md:text-9xl font-black tracking-tighter font-display text-black mb-2 relative z-10">
                                PLAN<br />IT.
                            </h1>

                            {/* Graphic Addition: Retro Pixel Earth */}
                            <motion.div
                                initial={{ scale: 0, rotate: -180 }}
                                animate={{ scale: 1, rotate: 0 }}
                                transition={{ delay: 0.5, duration: 1, type: "spring" }}
                                className="absolute -top-16 -right-16 w-32 h-32 z-20 pointer-events-none"
                            >
                                <svg viewBox="0 0 100 100" className="w-full h-full drop-shadow-[4px_4px_0px_rgba(0,0,0,1)]">
                                    <circle cx="50" cy="50" r="45" fill="#4B9CD3" stroke="black" strokeWidth="3" />
                                    <path d="M25,35 H35 V45 H45 V55 H35 V65 H25 V55 H15 V45 H25 Z" fill="#4CAF50" stroke="black" strokeWidth="1" />
                                    <path d="M65,25 H75 V35 H85 V45 H75 V55 H65 V45 H55 V35 H65 Z" fill="#4CAF50" stroke="black" strokeWidth="1" />
                                    <path d="M55,65 H65 V75 H75 V85 H65 V90 H55 V80 H45 V70 H55 Z" fill="#4CAF50" stroke="black" strokeWidth="1" />
                                    <path d="M20,20 Q50,10 80,20" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" opacity="0.6" />
                                    <ellipse cx="50" cy="50" rx="60" ry="15" fill="none" stroke="black" strokeWidth="2" strokeDasharray="4 4" transform="rotate(-30 50 50)" />
                                </svg>
                            </motion.div>

                            <p className="text-xl md:text-3xl font-bold font-mono tracking-tight text-black border-t-4 border-black pt-4 relative z-10">
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
