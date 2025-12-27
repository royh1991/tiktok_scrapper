import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

export async function GET(req: Request) {
    const { searchParams } = new URL(req.url);
    const tripId = searchParams.get('tripId');
    const queryId = searchParams.get('queryId');

    if (!tripId || !queryId) {
        return NextResponse.json({ error: 'tripId and queryId required' }, { status: 400 });
    }

    const PROJECT_ROOT = process.env.NEXT_PUBLIC_PROJECT_ROOT || '/Users/rhu/projects/tiktok_scrapper/';
    const tripPath = path.join(PROJECT_ROOT, 'trips', tripId);
    const queryPath = path.join(tripPath, queryId);
    const videosDir = path.join(queryPath, 'videos');

    try {
        const entries = await fs.readdir(videosDir, { withFileTypes: true });
        const tasks = entries
            .filter(entry => entry.isDirectory())
            .map(async (dir) => {
                const dirPath = path.join(videosDir, dir.name);

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

                return {
                    id: dir.name,
                    video_url: `/api/video?tripId=${tripId}&queryId=${queryId}&id=${dir.name}`, // Updated to include queryId if video streaming needs it? 
                    // Wait, api/video likely needs queryId too if it reads from the same structure!
                    // I will check api/video next, but for now I assume I need to pass queryId.
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
