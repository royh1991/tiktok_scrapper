
import { NextResponse } from 'next/server';
import { spawn } from 'child_process';

export async function POST(): Promise<NextResponse> {
    const scriptPath = '/Users/rhu/projects/tiktok_scrapper/process.py';
    const outputDir = '/Users/rhu/projects/tiktok_scrapper/output';
    // Ensure ANTHROPIC_API_KEY is available in the environment running this server
    // or default to one if provided in request (not doing that for security)

    return new Promise((resolve) => {
        console.log('Starting processing...');

        const pythonProcess = spawn('python', [
            scriptPath,
            '--output', outputDir,
            '--model', 'tiny' // Fast model
        ], {
            env: { ...process.env, ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY || '' }
        });

        let logs = '';

        pythonProcess.stdout.on('data', (data) => {
            logs += data.toString();
            console.log('Process:', data.toString());
        });

        pythonProcess.stderr.on('data', (data) => {
            console.error('Process Error:', data.toString());
        });

        pythonProcess.on('close', (code) => {
            if (code === 0) {
                resolve(NextResponse.json({ success: true, logs }));
            } else {
                resolve(NextResponse.json({ error: 'Processing failed', logs }, { status: 500 }));
            }
        });
    });
}
