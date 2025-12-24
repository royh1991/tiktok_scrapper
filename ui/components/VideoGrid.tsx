"use client";

import React from 'react';
import { VideoCard } from './VideoCard';
import { motion } from 'framer-motion';

interface VideoGridProps {
    videos: any[];
    onVideoClick: (video: any) => void;
}

export const VideoGrid = ({ videos, onVideoClick }: VideoGridProps) => {
    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 p-6">
            {videos.map((video, idx) => (
                <motion.div
                    key={video.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05 }}
                >
                    <VideoCard data={video} onClick={() => onVideoClick(video)} />
                </motion.div>
            ))}
        </div>
    );
};
