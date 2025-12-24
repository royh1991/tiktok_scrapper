"use client";

import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { motion } from 'framer-motion';

export const ThemeToggle = () => {
    // This is a mock implementation for the UI demo as we don't have a theme provider set up yet
    // In a real app, this would toggle the 'dark' class on html
    const [isDark, setIsDark] = React.useState(false);

    return (
        <button
            onClick={() => {
                setIsDark(!isDark);
                document.documentElement.classList.toggle('dark');
            }}
            className="p-2 rounded-full bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
            <motion.div
                initial={false}
                animate={{ rotate: isDark ? 180 : 0 }}
                transition={{ duration: 0.3 }}
            >
                {isDark ? <Moon className="w-5 h-5 text-indigo-400" /> : <Sun className="w-5 h-5 text-amber-500" />}
            </motion.div>
        </button>
    );
};
