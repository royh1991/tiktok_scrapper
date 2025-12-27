"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ProcessStepProps {
    title: string;
    description: string;
    status: 'waiting' | 'active' | 'completed' | 'error';
    index: number;
}

export const ProcessStep = ({ title, description, status, index }: ProcessStepProps) => {
    const isCompleted = status === 'completed';
    const isActive = status === 'active';

    return (
        <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className={cn(
                "relative p-4 border-2 transition-all duration-300",
                isActive ? "bg-white border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] z-10 scale-105 -rotate-1" : "border-transparent bg-transparent"
            )}
        >
            <div className="flex items-center gap-4">
                <div className="flex-shrink-0">
                    {isCompleted ? (
                        <div className="text-retro-green bg-black rounded-full p-0.5 border-2 border-black">
                            <CheckCircle2 className="w-6 h-6 text-retro-green" />
                        </div>
                    ) : isActive ? (
                        <Loader2 className="w-8 h-8 text-black animate-spin" />
                    ) : (
                        <Circle className="w-8 h-8 text-black/20" />
                    )}
                </div>

                <div className="flex-1 min-w-0">
                    <h3 className={cn(
                        "text-lg font-black font-display uppercase leading-none mb-1",
                        isCompleted && "text-black/50 line-through decoration-2 decoration-black/50",
                        isActive && "text-black",
                        status === 'waiting' && "text-black/30"
                    )}>
                        {title}
                    </h3>
                    <p className={cn(
                        "text-xs font-bold font-mono uppercase tracking-wide",
                        isActive ? "text-retro-blue" : "text-black/40"
                    )}>
                        {isActive ? (
                            <motion.span
                                animate={{ opacity: [1, 0.5, 1] }}
                                transition={{ repeat: Infinity, duration: 1.5 }}
                            >
                                {description}
                            </motion.span>
                        ) : description}
                    </p>
                </div>
            </div>
        </motion.div>
    );
};
