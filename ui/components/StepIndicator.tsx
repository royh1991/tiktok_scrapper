"use client";

import React from 'react';
import { motion } from 'framer-motion';

interface StepIndicatorProps {
    steps: number;
    currentStep: number;
}

export const StepIndicator = ({ steps, currentStep }: StepIndicatorProps) => {
    const progress = (currentStep / (steps - 1)) * 100;

    return (
        <div className="relative w-full h-4 bg-white border-2 border-black overflow-hidden shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
            <motion.div
                className="absolute top-0 left-0 h-full bg-retro-green border-r-2 border-black"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5, ease: "circOut" }}
            />
        </div>
    );
};
