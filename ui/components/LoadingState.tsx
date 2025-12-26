"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { FlightLoader } from './FlightLoader';
import { ProcessStep } from './ProcessStep';
import { StepIndicator } from './StepIndicator';
import { VisualStatus } from './VisualStatus';

interface LoadingStateProps {
    status: string; // 'searching', 'downloading', 'processing', 'complete'
    logs: string[]; // Recent status messages
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

    // Humanize the latest log for the visual display
    const getHumanizedLog = () => {
        const last = logs[logs.length - 1];
        if (!last) return null;

        if (last.includes('tiktok.com')) {
            const match = last.match(/@([^/]+)/);
            return match ? `Deep scouting insights from @${match[1]}...` : "Extracting travel secrets...";
        }
        if (last.toLowerCase().includes('downloading')) {
            return "Packing your personalized travel guide...";
        }
        if (last.toLowerCase().includes('processing')) {
            return "AI mapping your dream itinerary...";
        }
        return last;
    };

    return (
        <div className="w-full max-w-6xl mx-auto py-12 px-6">
            <div className="flex flex-col lg:flex-row gap-16 items-start">

                {/* Visual Action Area */}
                <div className="flex-1 w-full order-2 lg:order-1">
                    <div className="neo-card p-12 bg-white">
                        <VisualStatus
                            stage={status as any}
                            latestLog={getHumanizedLog() || steps[Math.min(currentStep, 2)].desc}
                        />
                    </div>
                </div>

                {/* Progress Tracking Sidebar */}
                <div className="w-full lg:w-96 order-1 lg:order-2">
                    <div className="mb-8 p-6 neo-card bg-retro-cream">
                        <motion.h2
                            className="text-4xl font-black mb-2 text-retro-black font-display uppercase tracking-tight"
                            key={status}
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                        >
                            {status === 'searching' ? 'Phase 1' :
                                status === 'downloading' ? 'Phase 2' : 'Phase 3'}
                        </motion.h2>
                        <p className="font-bold text-retro-black/50 uppercase tracking-widest text-xs border-b-2 border-black/10 pb-4">
                            Current Objective
                        </p>

                        <div className="mt-8 space-y-4">
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
                    </div>
                </div>
            </div>

            <div className="mt-12 max-w-md mx-auto">
                <StepIndicator steps={3} currentStep={currentStep} />
            </div>
        </div>
    );
};
