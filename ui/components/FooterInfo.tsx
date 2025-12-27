"use client";

import React from 'react';

export const FooterInfo = () => {
    return (
        <footer className="w-full py-8 text-center text-gray-400 text-sm border-t border-gray-100 dark:border-white/5 mt-auto">
            <p>
                Built with ❤️ by <span className="text-indigo-500 font-semibold">Gemini Agent</span>
            </p>
            <p className="mt-1 text-xs opacity-60">AI Vacation Planner Demo • {new Date().getFullYear()}</p>
        </footer>
    );
};
