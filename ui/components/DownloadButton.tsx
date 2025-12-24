"use client";

import React from 'react';
import { Button } from './ui/Button'; // Assuming Button is in ui/Button
import { Download } from 'lucide-react';

export const DownloadButton = ({ onClick }: { onClick: () => void }) => {
    return (
        <Button
            variant="secondary"
            size="sm"
            onClick={onClick}
            icon={<Download className="w-4 h-4" />}
            className="rounded-xl font-medium"
        >
            Download MP4
        </Button>
    );
};
