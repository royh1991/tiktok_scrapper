import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export const dynamic = 'force-dynamic';

const PROJECT_ROOT = process.env.NEXT_PUBLIC_PROJECT_ROOT || '';

export async function POST(req: Request) {
    try {
        const { tripId } = await req.json();
        const scriptPath = path.join(PROJECT_ROOT, 'tiktok_downloader.py');
        const tripPath = path.join(PROJECT_ROOT, 'trips', tripId);
        const inputFile = path.join(tripPath, 'urls.txt');
        const outputDir = path.join(tripPath, 'videos');

        console.log(`Starting downloader for trip: ${tripId}`);

        const pythonProcess = spawn('python', [
            scriptPath,
            '--dev',
            '--output', outputDir,
            'download',
            '--file', inputFile
        ]);

        const stream = new ReadableStream({
            start(controller) {
                pythonProcess.stdout.on('data', (data) => controller.enqueue(data));
                pythonProcess.stderr.on('data', (data) => controller.enqueue(data));
                pythonProcess.on('close', (code) => {
                    if (code !== 0) {
                        controller.enqueue(Buffer.from(`\nError: Downloader exited with code ${code}`));
                    }
                    controller.close();
                });
            }
        });

        return new Response(stream, {
            headers: {
                'Content-Type': 'text/plain; charset=utf-8',
                'Transfer-Encoding': 'chunked',
            },
        });

    } catch (error: any) {
        console.error('Download API Error:', error);
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
