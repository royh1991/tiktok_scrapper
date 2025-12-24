import React from 'react';
import { cn } from '@/lib/utils';
import { motion, HTMLMotionProps } from 'framer-motion';

interface CardProps extends HTMLMotionProps<"div"> {
    variant?: 'glass' | 'solid' | 'outline';
}

export const Card = ({ className, variant = 'glass', children, ...props }: CardProps) => {
    const variants = {
        glass: 'bg-white/70 dark:bg-black/40 backdrop-blur-xl border border-white/20 dark:border-white/10 shadow-xl',
        solid: 'bg-white dark:bg-gray-900 shadow-md border border-gray-100 dark:border-gray-800',
        outline: 'bg-transparent border-2 border-dashed border-gray-300 dark:border-gray-700',
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className={cn(
                'rounded-3xl overflow-hidden p-6',
                variants[variant],
                className
            )}
            {...props}
        >
            {children}
        </motion.div>
    );
};
