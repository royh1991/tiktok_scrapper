import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export const dynamic = 'force-dynamic';

const PROJECT_ROOT = process.env.NEXT_PUBLIC_PROJECT_ROOT || '';

export async function POST(req: Request) {
    try {
        const { query, tripId, queryId } = await req.json();

        if (!tripId || !queryId) {
            throw new Error("Missing tripId or queryId");
        }

        const scriptPath = path.join(PROJECT_ROOT, 'tiktok_search.py');
        const tripPath = path.join(PROJECT_ROOT, 'trips', tripId);
        const queryPath = path.join(tripPath, queryId);
        const outputPath = path.join(queryPath, 'urls.txt');

        console.log(`Starting binary search for: ${query} in trip: ${tripId} / ${queryId}`);

        const pythonProcess = spawn('python', [
            scriptPath,
            query,
            '--max', '30',
            '-o', outputPath
        ]);

        const stream = new ReadableStream({
            start(controller) {
                pythonProcess.stdout.on('data', (data) => {
                    controller.enqueue(data);
                });

                pythonProcess.stderr.on('data', (data) => {
                    const text = data.toString();
                    if (!text.includes('Progress:')) {
                        controller.enqueue(data);
                    }
                });

                pythonProcess.on('close', (code) => {
                    if (code !== 0) {
                        controller.enqueue(Buffer.from(`\nError: Search script exited with code ${code}`));
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
        console.error('Search API Error:', error);
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
