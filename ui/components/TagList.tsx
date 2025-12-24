"use client";

import React, { useRef } from 'react';
import { TagPill } from '@/components/ui/Badge';
import { ArrowRight, Scroll } from 'lucide-react';

interface TagListProps {
    tags: string[];
    onTagClick: (tag: string) => void;
}

export const TagList = ({ tags, onTagClick }: TagListProps) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    return (
        <div className="relative group w-full overflow-hidden">
            <div
                ref={scrollRef}
                className="flex items-center gap-3 overflow-x-auto pb-4 pt-2 px-1 scrollbar-hide mask-fade"
            >
                {tags.map((tag) => (
                    <div key={tag} className="flex-shrink-0">
                        <TagPill tag={tag} onClick={() => onTagClick(tag)} />
                    </div>
                ))}
            </div>

            {/* Fade edges */}
            <div className="absolute left-0 top-0 bottom-4 w-12 bg-gradient-to-r from-white dark:from-black to-transparent pointer-events-none" />
            <div className="absolute right-0 top-0 bottom-4 w-12 bg-gradient-to-l from-white dark:from-black to-transparent pointer-events-none" />
        </div>
    );
};
