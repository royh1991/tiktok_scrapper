import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const OUTPUT_DIR = '/Users/rhu/projects/tiktok_scrapper/output';

export async function GET() {
    try {
        const entries = await fs.readdir(OUTPUT_DIR, { withFileTypes: true });
        const tasks = entries
            .filter(entry => entry.isDirectory())
            .map(async (dir) => {
                const dirPath = path.join(OUTPUT_DIR, dir.name);

                // Read metadata.json
                let metadata: any = { creator_nickname: 'Unknown', caption: 'No caption' };
                try {
                    const metaContent = await fs.readFile(path.join(dirPath, 'metadata.json'), 'utf-8');
                    metadata = JSON.parse(metaContent);
                } catch (e) { }

                // Check for transcript
                let transcriptPreview = '';
                let hasTranscript = false;
                try {
                    const transcript = await fs.readFile(path.join(dirPath, 'transcript.txt'), 'utf-8');
                    hasTranscript = true;
                    transcriptPreview = transcript.substring(0, 150) + '...';
                } catch (e) { }

                // Check video path for serving
                // In a real app we'd serve via /api/video/[id] or static hosting
                // For now we assume local dev can access file system or we proxy
                // To make it simple for the frontend, we'll need a route to stream video bytes
                // or configure next.js to serve this folder statically?
                // Let's create an API route to serve video content: /api/video?path=...

                return {
                    id: dir.name,
                    video_url: `/api/video?id=${dir.name}`, // Proxy route we need to make
                    metadata,
                    hasTranscript,
                    transcriptPreview
                };
            });

        const videos = await Promise.all(tasks);
        return NextResponse.json({ videos });

    } catch (error) {
        console.error('Results Error:', error);
        return NextResponse.json({ error: 'Failed to fetch results', videos: [] }, { status: 500 });
    }
}
