import React from 'react';
import { cn } from '@/lib/utils';
import { Search } from 'lucide-react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    icon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
    ({ className, icon, ...props }, ref) => {
        return (
            <div className="relative group w-full">
                <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none text-gray-500 group-focus-within:text-indigo-500 transition-colors">
                    {icon || <Search className="w-5 h-5" />}
                </div>
                <input
                    ref={ref}
                    className={cn(
                        'w-full pl-12 pr-4 py-4 rounded-2xl bg-white/80 dark:bg-white/5 backdrop-blur-md border border-gray-200 dark:border-white/10 focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 outline-none transition-all duration-300 placeholder:text-gray-400 text-lg shadow-sm group-hover:shadow-md',
                        className
                    )}
                    {...props}
                />
            </div>
        );
    }
);

Input.displayName = 'Input';
