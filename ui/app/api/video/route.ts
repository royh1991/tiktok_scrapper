import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import { createReadStream } from 'fs';
import path from 'path';

export async function GET(req: Request) {
    const { searchParams } = new URL(req.url);
    const tripId = searchParams.get('tripId');
    const videoId = searchParams.get('id');

    if (!tripId || !videoId) {
        return NextResponse.json({ error: 'tripId and id required' }, { status: 400 });
    }

    const PROJECT_ROOT = process.env.NEXT_PUBLIC_PROJECT_ROOT || '/Users/rhu/projects/tiktok_scrapper/';
    const videoPath = path.join(PROJECT_ROOT, 'trips', tripId, 'videos', videoId, 'video.mp4');

    try {
        const stats = await fs.stat(videoPath);
        const stream = createReadStream(videoPath);

        return new Response(stream as any, {
            headers: {
                'Content-Type': 'video/mp4',
                'Content-Length': stats.size.toString(),
            },
        });
    } catch (error) {
        console.error('Video serve error:', error);
        return NextResponse.json({ error: 'Video not found' }, { status: 404 });
    }
}
