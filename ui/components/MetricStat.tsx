"use client";

import React from 'react';
import { cn } from '@/lib/utils';

interface MetricStatProps {
    icon: React.ReactNode;
    value: string | number;
    label?: string;
    className?: string;
}

export const MetricStat = ({ icon, value, label, className }: MetricStatProps) => (
    <div className={cn("flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300", className)}>
        <span className="text-gray-400 dark:text-gray-500">{icon}</span>
        <span className="font-semibold">{value}</span>
        {label && <span className="text-gray-400 font-light">{label}</span>}
    </div>
);
