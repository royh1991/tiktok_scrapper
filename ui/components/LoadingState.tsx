"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { FlightLoader } from './FlightLoader';
import { ProcessStep } from './ProcessStep';
import { StepIndicator } from './StepIndicator';

interface LoadingStateProps {
    status: string; // 'searching', 'downloading', 'processing', 'complete'
    logs: string[]; // Recent status messages (e.g. "Downloading video 3/50")
}

export const LoadingState = ({ status, logs }: LoadingStateProps) => {

    const getStepIndex = () => {
        switch (status) {
            case 'searching': return 0;
            case 'downloading': return 1;
            case 'processing': return 2;
            case 'complete': return 3;
            default: return 0;
        }
    };

    const steps = [
        { id: 'search', title: 'Scouting Locations', desc: 'Searching TikTok for the best videos...' },
        { id: 'download', title: 'Collecting Memories', desc: 'Downloading high-quality footage...' },
        { id: 'process', title: 'Analyzing Content', desc: 'Extracting itineraries and hidden gems...' },
    ];

    const currentStep = getStepIndex();

    return (
        <div className="w-full max-w-2xl mx-auto py-12 px-6">
            <div className="text-center mb-12">
                <FlightLoader />
                <motion.h2
                    className="text-2xl font-bold mt-8 text-gray-800 dark:text-white"
                    key={status} // Animate on change
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                >
                    {steps[Math.min(currentStep, 2)].title}
                </motion.h2>
                <p className="text-gray-500 mt-2 min-h-[1.5em]">
                    {logs[logs.length - 1] || steps[Math.min(currentStep, 2)].desc}
                </p>
            </div>

            <div className="space-y-4 mb-8">
                {steps.map((step, idx) => (
                    <ProcessStep
                        key={step.id}
                        index={idx}
                        title={step.title}
                        description={step.desc}
                        status={
                            currentStep > idx ? 'completed' :
                                currentStep === idx ? 'active' : 'waiting'
                        }
                    />
                ))}
            </div>

            <StepIndicator steps={3} currentStep={currentStep} />
        </div>
    );
};
