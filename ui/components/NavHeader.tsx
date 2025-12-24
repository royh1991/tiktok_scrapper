"use client";

import React from 'react';
import Link from 'next/link';
import { Compass } from 'lucide-react';

export const NavHeader = () => {
    return (
        <header className="absolute top-0 w-full z-40 px-6 py-6 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 group">
                <div className="p-2 bg-white/10 backdrop-blur-md rounded-xl border border-white/20 group-hover:bg-white/20 transition-colors">
                    <Compass className="w-6 h-6 text-white" />
                </div>
                <span className="text-xl font-bold text-white tracking-tight drop-shadow-md">
                    Wanderlust<span className="text-blue-400">AI</span>
                </span>
            </Link>

            <nav className="hidden md:flex items-center gap-6">
                <a href="#" className="text-sm font-medium text-white/80 hover:text-white hover:underline transition-colors decoration-blue-400 decoration-2 underline-offset-4">Discover</a>
                <a href="#" className="text-sm font-medium text-white/80 hover:text-white transition-colors">Saved Trips</a>
            </nav>
        </header>
    );
};
