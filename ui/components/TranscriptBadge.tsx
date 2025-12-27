"use client";

import React from 'react';
import { FileText } from 'lucide-react';
import { motion } from 'framer-motion';

export const TranscriptBadge = ({ hasTranscript }: { hasTranscript: boolean }) => {
    if (!hasTranscript) return null;

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-100/80 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 text-[10px] font-bold uppercase tracking-wider backdrop-blur-sm border border-emerald-200/50 dark:border-emerald-800/30"
        >
            <FileText className="w-3 h-3" />
            <span>AI Transcript</span>
        </motion.div>
    );
};
