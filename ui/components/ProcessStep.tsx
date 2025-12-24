"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/Card';

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
        >
            <Card
                variant={isActive ? 'glass' : 'solid'}
                className={cn(
                    "flex items-center gap-4 py-4 transition-all duration-300",
                    isActive && "ring-2 ring-indigo-500 bg-white/90",
                    status === 'waiting' && "opacity-60 bg-transparent shadow-none border-transparent"
                )}
            >
                <div className="flex-shrink-0">
                    {isCompleted ? (
                        <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            className="text-green-500"
                        >
                            <CheckCircle2 className="w-8 h-8" />
                        </motion.div>
                    ) : isActive ? (
                        <div className="relative">
                            <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                            <motion.div
                                className="absolute inset-0 bg-indigo-500/20 rounded-full blur-lg"
                                animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
                                transition={{ repeat: Infinity, duration: 2 }}
                            />
                        </div>
                    ) : (
                        <Circle className="w-8 h-8 text-gray-300 dark:text-gray-700" />
                    )}
                </div>

                <div className="flex-1 min-w-0">
                    <h3 className={cn(
                        "text-lg font-semibold",
                        isCompleted && "text-gray-900 dark:text-white",
                        isActive && "text-indigo-600 dark:text-indigo-400",
                        status === 'waiting' && "text-gray-400"
                    )}>
                        {title}
                    </h3>
                    <p className="text-sm text-gray-500 truncate">
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
            </Card>
        </motion.div>
    );
};
