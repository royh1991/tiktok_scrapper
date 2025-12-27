import React from 'react';
import { cn } from '@/lib/utils';

interface BadgeProps {
    children: React.ReactNode;
    variant?: 'default' | 'outline' | 'secondary' | 'accent';
    className?: string;
}

export const Badge = ({ children, variant = 'default', className }: BadgeProps) => {
    const variants = {
        default: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300',
        outline: 'border border-gray-200 text-gray-600 dark:border-gray-700 dark:text-gray-400',
        secondary: 'bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100',
        accent: 'bg-pink-100 text-pink-700 dark:bg-pink-500/20 dark:text-pink-300',
    };

    return (
        <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors', variants[variant], className)}>
            {children}
        </span>
    );
};

export const TagPill = ({ tag, onClick }: { tag: string; onClick?: () => void }) => (
    <button
        onClick={onClick}
        className="group relative inline-flex items-center px-4 py-1.5 rounded-full bg-white/50 dark:bg-black/20 backdrop-blur-sm border border-gray-200 dark:border-white/10 hover:border-indigo-500 transition-all duration-300"
    >
        <span className="text-indigo-500 mr-1 opacity-70 group-hover:opacity-100">#</span>
        <span className="text-gray-700 dark:text-gray-300 text-sm font-medium group-hover:text-indigo-600 dark:group-hover:text-indigo-400">
            {tag}
        </span>
    </button>
);
