"use client";

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ToastProps {
    message: string;
    type?: 'success' | 'error';
    isVisible: boolean;
    onClose: () => void;
}

export const Toast = ({ message, type = 'success', isVisible, onClose }: ToastProps) => {
    return (
        <AnimatePresence>
            {isVisible && (
                <motion.div
                    initial={{ opacity: 0, y: 50, scale: 0.9 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 20, scale: 0.9 }}
                    className={cn(
                        "fixed bottom-8 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-full shadow-2xl backdrop-blur-md flex items-center gap-3 border",
                        type === 'success' ? "bg-white/90 text-green-800 border-green-200" : "bg-red-50 text-red-800 border-red-200",
                        "dark:bg-gray-800 dark:border-gray-700"
                    )}
                >
                    {type === 'success' ? <CheckCircle className="w-5 h-5 text-green-500" /> : <XCircle className="w-5 h-5 text-red-500" />}
                    <span className="font-medium">{message}</span>
                </motion.div>
            )}
        </AnimatePresence>
    );
};
