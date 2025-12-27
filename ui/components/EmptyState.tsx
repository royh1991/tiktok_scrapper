"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { SearchX } from 'lucide-react';

export const EmptyState = ({ message = "No videos found. Try a different search!" }: { message?: string }) => {
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-20 text-center"
        >
            <div className="w-24 h-24 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center mb-6">
                <SearchX className="w-10 h-10 text-gray-400" />
            </div>
            <h3 className="text-xl font-semibold text-gray-700 dark:text-gray-300">Nothing here yet</h3>
            <p className="text-gray-500 mt-2 max-w-sm mx-auto">{message}</p>
        </motion.div>
    );
};
