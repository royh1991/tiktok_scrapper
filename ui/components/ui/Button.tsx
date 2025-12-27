import React, { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';
import { motion, HTMLMotionProps } from 'framer-motion';

interface ButtonProps extends HTMLMotionProps<"button"> {
    variant?: 'primary' | 'secondary' | 'ghost' | 'outline';
    size?: 'sm' | 'md' | 'lg';
    icon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant = 'primary', size = 'md', children, icon, ...props }, ref) => {

        const variants = {
            primary: 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg hover:shadow-xl hover:scale-[1.02]',
            secondary: 'bg-white/10 backdrop-blur-md text-white border border-white/20 hover:bg-white/20',
            ghost: 'bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-white/10',
            outline: 'border-2 border-indigo-500 text-indigo-500 hover:bg-indigo-50',
        };

        const sizes = {
            sm: 'px-3 py-1.5 text-sm',
            md: 'px-6 py-3 text-base',
            lg: 'px-8 py-4 text-lg font-semibold',
        };

        return (
            <motion.button
                ref={ref}
                whileTap={{ scale: 0.98 }}
                className={cn(
                    'relative inline-flex items-center justify-center gap-2 rounded-full transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed',
                    variants[variant],
                    sizes[size],
                    className
                )}
                {...props}
            >
                {icon && <span className="w-5 h-5">{icon}</span>}
                {children}
            </motion.button>
        );
    }
);

Button.displayName = 'Button';
