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
            whileHover={{ y: -5, rotate: 1 }}
            className="group cursor-default h-full"
        >
            <div className="neo-card p-3 h-full flex flex-col bg-white overflow-hidden transform transition-all hover:shadow-[var(--shadow-neo-lg)]">
                {/* Video Preview - "Polaroid" Style */}
                <div className="relative aspect-[9/16] bg-black border-2 border-black overflow-hidden cursor-pointer mb-3" onClick={togglePlay}>
                    <video
                        ref={videoRef}
                        src={data.video_url}
                        className="w-full h-full object-cover opacity-90 group-hover:scale-105 transition-transform duration-700 filter contrast-125"
                        muted
                        loop
                        playsInline
                    />

                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-80 pointer-events-none" />

                    {/* Overlay Badges */}
                    <div className="absolute top-3 left-3 flex flex-wrap gap-2">
                        <TranscriptBadge hasTranscript={data.hasTranscript} />
                    </div>

                    {/* Play/Pause Button Overlay */}
                    <div className={`absolute inset-0 flex items-center justify-center transition-opacity duration-300 pointer-events-none ${isPlaying ? 'opacity-0' : 'opacity-100'}`}>
                        <div className="w-16 h-16 bg-retro-yellow border-4 border-black flex items-center justify-center shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                            <Play className="w-8 h-8 text-black fill-current translate-x-1" />
                        </div>
                    </div>
                </div>

                {/* Content Body */}
                <div className="flex-1 flex flex-col gap-2">
                    <div className="flex items-start justify-between">
                        <div className="font-display font-bold text-lg leading-tight line-clamp-2">
                            {data.metadata.caption || "Untitled Memory"}
                        </div>
                    </div>

                    <div className="flex items-center gap-2 text-xs font-bold font-mono uppercase tracking-tight text-gray-500 border-b-2 border-dashed border-gray-200 pb-2 mb-1">
                        <User className="w-3 h-3" />
                        {data.metadata.creator_nickname || 'Unknown Creator'}
                    </div>

                    <AnimatePresence>
                        {isExpanded && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="overflow-hidden"
                            >
                                {data.transcriptPreview && (
                                    <div className="text-xs bg-retro-cream p-3 border-2 border-black mt-2 font-mono leading-relaxed">
                                        <div className="font-bold text-[10px] uppercase tracking-wider text-black/50 mb-1">Transcript Data</div>
                                        "{data.transcriptPreview}"
                                    </div>
                                )}
                                <div className="mt-3 text-xs text-black leading-relaxed font-medium">
                                    {data.metadata.caption}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    <div className="mt-auto flex items-center justify-between pt-2">
                        <button
                            onClick={() => setIsExpanded(!isExpanded)}
                            className="flex items-center gap-1 text-xs font-bold text-black hover:text-retro-blue transition-colors uppercase tracking-wider"
                        >
                            {isExpanded ? 'Hide Info' : 'View Info'}
                            {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>

                        <div className="flex items-center gap-2">
                            <MetricStat icon={<Heart className="w-3 h-3" />} value="--" />
                            <Badge variant="outline" className="text-[10px] border-black text-black font-bold">TikTok</Badge>
                        </div>
                    </div>
                </div>
            </div>
        </motion.div>
    );
};
