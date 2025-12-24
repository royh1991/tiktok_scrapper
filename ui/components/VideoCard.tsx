"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { Card } from '@/components/ui/Card';
import { Badge, TagPill } from '@/components/ui/Badge';
import { MetricStat } from './MetricStat';
import { TranscriptBadge } from './TranscriptBadge';
import { Play, Heart, MessageCircle, User } from 'lucide-react';
import Image from 'next/image';

interface VideoData {
    id: string;
    video_url: string; // Path to local video or TikTok URL
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
    thumbnailUrl?: string; // Optional if we generate thumbs, else video poster
}

interface VideoCardProps {
    data: VideoData;
    onClick: () => void;
}

export const VideoCard = ({ data, onClick }: VideoCardProps) => {
    return (
        <motion.div
            whileHover={{ y: -5 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            onClick={onClick}
            className="group cursor-pointer h-full"
        >
            <Card variant="glass" className="p-0 h-full flex flex-col bg-white/40 border-white/40 dark:bg-black/40">
                {/* Video Preview / Texture */}
                <div className="relative aspect-[9/16] bg-gray-100 dark:bg-gray-800 overflow-hidden">
                    <video
                        src={data.video_url}
                        className="w-full h-full object-cover opacity-90 group-hover:scale-105 transition-transform duration-700"
                        muted
                        loop
                        playsInline
                        onMouseOver={(e) => e.currentTarget.play()}
                        onMouseOut={(e) => {
                            e.currentTarget.pause();
                            e.currentTarget.currentTime = 0;
                        }}
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
                        <p className="text-sm line-clamp-2 leading-snug opacity-95">
                            {data.metadata.caption}
                        </p>
                    </div>

                    {/* Play Button Overlay */}
                    <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
                        <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center border border-white/40">
                            <Play className="w-5 h-5 text-white fill-current translate-x-0.5" />
                        </div>
                    </div>
                </div>

                {/* Content Body */}
                <div className="p-4 flex-1 flex flex-col gap-3">
                    {/* Transcript Preview */}
                    {data.transcriptPreview && (
                        <div className="text-xs text-gray-500 dark:text-gray-400 line-clamp-3 italic bg-gray-50 dark:bg-white/5 p-2 rounded-lg border border-gray-100 dark:border-white/5">
                            "{data.transcriptPreview}"
                        </div>
                    )}

                    <div className="mt-auto pt-2 flex items-center justify-between border-t border-gray-100 dark:border-white/10">
                        <div className="flex items-center gap-4">
                            <MetricStat icon={<Heart className="w-3 h-3" />} value="--" /> {/* Placeholder stats if not scraped */}
                            <MetricStat icon={<MessageCircle className="w-3 h-3" />} value="--" />
                        </div>
                        <Badge variant="outline" className="text-[10px]">Details</Badge>
                    </div>
                </div>
            </Card>
        </motion.div>
    );
};
