"use client";

import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal, Shield, CheckCircle, Search, Download, Sparkles, MapPin } from 'lucide-react';

interface Props {
    logs: string[];
}

export const LiveTicker = ({ logs }: Props) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    const parseLog = (log: string) => {
        const text = log.trim();

        // 1. Filter out absolute noise
        if (text.includes('DeprecationWarning')) return null;
        if (text.includes('Saved to:')) return { text: "Search results indexed.", icon: <CheckCircle className="w-3 h-3 text-green-400" /> };
        if (text.includes('Run: python')) return null;
        if (text.startsWith('===') || text.startsWith('---')) return null;
        if (text.includes('/Users/')) return null; // Don't show local paths

        // 2. Transform TikTok URLs
        const tiktokMatch = text.match(/https:\/\/www\.tiktok\.com\/@([^/]+)\/video\/(\d+)/);
        if (tiktokMatch) {
            const username = tiktokMatch[1];
            return {
                text: `Successfully scouted recommendations from @${username}`,
                icon: <MapPin className="w-3 h-3 text-indigo-400" />
            };
        }

        // 3. Humanize standard statuses
        if (text.toLowerCase().includes('found')) {
            return { text: text.replace(/via [^)]+/g, '').trim(), icon: <Search className="w-3 h-3 text-blue-400" /> };
        }
        if (text.toLowerCase().includes('downloading')) {
            const parts = text.split('/');
            const progress = parts.length > 1 ? `(${parts[0].split(' ').pop()}/${parts[1]})` : "";
            return { text: `Downloading high-fidelity travel footage ${progress}`, icon: <Download className="w-3 h-3 text-indigo-400" /> };
        }
        if (text.toLowerCase().includes('processing') || text.toLowerCase().includes('analyzing')) {
            return { text: "AI is analyzing video highlights for your itinerary...", icon: <Sparkles className="w-3 h-3 text-purple-400" /> };
        }

        // Fallback for anything else meaningful
        if (text.length < 5 || text.includes('Traceback')) return null;

        return { text: text, icon: <Terminal className="w-4 h-4 text-slate-500" /> };
    };

    const parsedLogs = logs.map(parseLog).filter(Boolean) as { text: string; icon: React.ReactNode }[];

    return (
        <div className="w-full bg-slate-950/80 backdrop-blur-xl rounded-[2rem] border border-white/10 p-5 shadow-2xl relative overflow-hidden">
            <div className="flex items-center gap-2 mb-4 text-slate-400 border-b border-white/5 pb-3">
                <div className="p-1.5 bg-indigo-500/10 rounded-lg">
                    <Shield className="w-4 h-4 text-indigo-400" />
                </div>
                <span className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-500">Live Mission Feed</span>
            </div>

            <div
                ref={scrollRef}
                className="h-56 overflow-y-auto space-y-3 scrollbar-none pr-2 pt-1"
            >
                <AnimatePresence initial={false}>
                    {parsedLogs.map((log, i) => (
                        <motion.div
                            key={`${i}-${log.text.slice(0, 20)}`}
                            initial={{ opacity: 0, x: -10, filter: 'blur(4px)' }}
                            animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
                            className="flex items-start gap-3 text-xs font-medium leading-relaxed text-slate-300 group"
                        >
                            <div className="mt-0.5 opacity-60 group-hover:opacity-100 transition-opacity">
                                {log.icon}
                            </div>
                            <div className="flex-1">
                                {log.text}
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>
            </div>

            <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-slate-950 to-transparent pointer-events-none" />
        </div>
    );
};
