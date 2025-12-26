"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { Card } from '@/components/ui/Card';
import { Badge, TagPill } from '@/components/ui/Badge';
import { MetricStat } from './MetricStat';
import { TranscriptBadge } from './TranscriptBadge';
import { Play, Heart, MessageCircle, User, ChevronDown, ChevronUp } from 'lucide-react';
import Image from 'next/image';
import { AnimatePresence } from 'framer-motion';

interface VideoData {
    id: string;
    video_url: string;
    metadata: {
        creator_nickname: string;
        caption: string;
        stats?: {
            plays: string;
            likes: string;
        }
    };
    hasTranscript: boolean;
    transcriptPreview?: string;
    thumbnailUrl?: string;
}

interface VideoCardProps {
    data: VideoData;
    onClick?: () => void;
}

export const VideoCard = ({ data, onClick }: VideoCardProps) => {
    const [isExpanded, setIsExpanded] = React.useState(false);
    const [isPlaying, setIsPlaying] = React.useState(false);
    const videoRef = React.useRef<HTMLVideoElement>(null);

    const togglePlay = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!videoRef.current) return;

        if (isPlaying) {
            videoRef.current.pause();
        } else {
            videoRef.current.play();
        }
        setIsPlaying(!isPlaying);
    };

    return (
        <motion.div
            whileHover={{ y: -5 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            className="group cursor-default h-full"
        >
            <Card variant="glass" className="p-0 h-full flex flex-col bg-white/40 border-white/40 dark:bg-black/40 overflow-hidden">
                {/* Video Preview */}
                <div className="relative aspect-[9/16] bg-gray-100 dark:bg-gray-800 overflow-hidden cursor-pointer" onClick={togglePlay}>
                    <video
                        ref={videoRef}
                        src={data.video_url}
                        className="w-full h-full object-cover opacity-90 group-hover:scale-105 transition-transform duration-700"
                        muted
                        loop
                        playsInline
                    />

                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-60 pointer-events-none" />

                    {/* Overlay Badges */}
                    <div className="absolute top-3 left-3 flex flex-wrap gap-2">
                        <TranscriptBadge hasTranscript={data.hasTranscript} />
                    </div>

                    <div className="absolute bottom-3 left-3 right-3 text-white">
                        <div className="flex items-center gap-2 mb-2 text-xs font-semibold opacity-90">
                            <User className="w-3 h-3" />
                            {data.metadata.creator_nickname || 'Unknown Creator'}
                        </div>
                        <p className={`text-sm leading-snug opacity-95 ${isExpanded ? '' : 'line-clamp-2'}`}>
                            {data.metadata.caption}
                        </p>
                    </div>

                    {/* Play/Pause Button Overlay */}
                    <div className={`absolute inset-0 flex items-center justify-center transition-opacity duration-300 pointer-events-none ${isPlaying ? 'opacity-0' : 'opacity-100'}`}>
                        <div className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center border border-white/40 shadow-xl">
                            <Play className="w-6 h-6 text-white fill-current translate-x-0.5" />
                        </div>
                    </div>
                </div>

                {/* Content Body */}
                <div className="p-4 flex-1 flex flex-col gap-3">
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="flex items-center justify-between w-full text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 transition-colors"
                    >
                        {isExpanded ? 'Hide Details' : 'Show Details'}
                        {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </button>

                    <AnimatePresence>
                        {isExpanded && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="overflow-hidden"
                            >
                                {data.transcriptPreview && (
                                    <div className="text-xs text-gray-500 dark:text-gray-400 italic bg-gray-50 dark:bg-white/5 p-3 rounded-xl border border-gray-100 dark:border-white/5 mt-2">
                                        <div className="font-bold text-[10px] uppercase tracking-wider text-gray-400 mb-1 not-italic">Transcript</div>
                                        "{data.transcriptPreview}"
                                    </div>
                                )}
                                <div className="mt-3 text-xs text-gray-600 dark:text-gray-300 leading-relaxed">
                                    {data.metadata.caption}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    <div className="mt-auto pt-2 flex items-center justify-between border-t border-gray-100 dark:border-white/10">
                        <div className="flex items-center gap-4">
                            <MetricStat icon={<Heart className="w-3 h-3" />} value="--" />
                            <MetricStat icon={<MessageCircle className="w-3 h-3" />} value="--" />
                        </div>
                        <Badge variant="outline" className="text-[10px] opacity-50">TikTok</Badge>
                    </div>
                </div>
            </Card>
        </motion.div>
    );
};
