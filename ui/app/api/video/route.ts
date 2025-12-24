import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(req: Request) {
    const { searchParams } = new URL(req.url);
    const id = searchParams.get('id');

    if (!id) {
        return new NextResponse('Missing ID', { status: 400 });
    }

    const outputDir = '/Users/rhu/projects/tiktok_scrapper/output';
    const videoPathMp4 = path.join(outputDir, id, 'video.mp4');
    // const videoPathWebm = path.join(outputDir, id, 'video.webm');

    // Simple serving logic
    if (fs.existsSync(videoPathMp4)) {
        const stat = fs.statSync(videoPathMp4);
        const fileSize = stat.size;
        const stream = fs.createReadStream(videoPathMp4);

        // @ts-ignore
        return new NextResponse(stream, {
            headers: {
                'Content-Type': 'video/mp4',
                'Content-Length': fileSize.toString(),
            }
        });
    }

    return new NextResponse('Video not found', { status: 404 });
}
