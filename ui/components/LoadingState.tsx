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

    // Playful startup messages to fill the void while Python warms up
    const [startupLog, setStartupLog] = React.useState<string>("");

    React.useEffect(() => {
        if (logs.length > 0) return; // Stop fake logs once real ones arrive

        const startupMessages = [
            "Fueling the jet...",
            "Checking passport validity...",
            "Contacting local guides...",
            "Unfolding map...",
            "Brewing coffee for the pilot..."
        ];

        let i = 0;
        setStartupLog(startupMessages[0]);

        const interval = setInterval(() => {
            if (i < startupMessages.length - 1) {
                i++;
                setStartupLog(startupMessages[i]);
            }
        }, 5000); // 5 seconds per message, no loop

        return () => clearInterval(interval);
    }, [logs.length]);

    // Humanize the latest log for the visual display
    // Humanize the log, prioritizing important success messages from the recent history
    const getHumanizedLog = () => {
        // Look at the last 20 logs to find a 'success' or 'scouting' message
        // This prevents the status from flickering if a boring log comes right after an interesting one
        const recentLogs = logs.slice(-20).reverse();

        const successLog = recentLogs.find(l => l.includes('DOWNLOAD_SUCCESS:'));
        if (successLog) {
            const clean = successLog.replace('DOWNLOAD_SUCCESS:', '').trim();
            return `Downloaded: ${clean}`;
        }

        const scoutingLog = recentLogs.find(l => l.includes('tiktok.com') && l.includes('@'));
        if (scoutingLog) {
            const match = scoutingLog.match(/@([^/]+)/);
            return match ? `Deep scouting insights from @${match[1]}...` : "Extracting travel secrets...";
        }

        // Fallback to the very last log if no priority message found
        const last = logs[logs.length - 1];
        if (!last) return null;

        // FILTER: Ignore raw code/technical logs
        if (last.includes('await self.') || last.includes('cdp_') || last.includes('result =')) {
            return null;
        }

        if (last.toLowerCase().includes('downloading')) {
            return "Packing your personalized travel guide...";
        }
        if (last.toLowerCase().includes('processing')) {
            return "AI mapping your dream itinerary...";
        }
        return last;
    };

    // Use the computed human log, or fall back to the startup animation log
    const displayLog = getHumanizedLog() || startupLog || steps[Math.min(currentStep, 2)].desc;

    return (
        <div className="w-full max-w-6xl mx-auto py-12 px-6">
            <div className="flex flex-col lg:flex-row gap-16 items-start">

                {/* Visual Action Area */}
                <div className="flex-1 w-full order-2 lg:order-1">
                    <div className="neo-card p-12 bg-white">
                        <VisualStatus
                            stage={status as any}
                            latestLog={displayLog}
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
