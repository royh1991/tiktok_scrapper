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
        <div className="relative w-full h-1 bg-gray-200 dark:bg-gray-800 rounded-full overflow-hidden">
            <motion.div
                className="absolute top-0 left-0 h-full bg-gradient-to-r from-blue-500 to-purple-500"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5, ease: "easeInOut" }}
            />
        </div>
    );
};
