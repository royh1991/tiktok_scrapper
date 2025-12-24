import { NextResponse } from 'next/server';
import { spawn } from 'child_process';

export async function POST(): Promise<NextResponse> {
    const scriptPath = '/Users/rhu/projects/tiktok_scrapper/tiktok_downloader.py';
    const inputFile = '/Users/rhu/projects/tiktok_scrapper/search_results.txt';
    const outputDir = '/Users/rhu/projects/tiktok_scrapper/output';

    return new Promise((resolve) => {
        // Run: python3 tiktok_downloader.py download --file search_results.txt --output output
        console.log('Starting downloader...');

        const pythonProcess = spawn('python', [
            scriptPath,
            '--dev',
            'download',
            '--file', inputFile
        ]);

        let logs = '';

        pythonProcess.stdout.on('data', (data) => {
            logs += data.toString();
            console.log('Download:', data.toString());
        });

        pythonProcess.stderr.on('data', (data) => {
            console.error('Download Error:', data.toString());
        });

        pythonProcess.on('close', (code) => {
            if (code === 0) {
                resolve(NextResponse.json({ success: true, logs }));
            } else {
                resolve(NextResponse.json({ error: 'Download failed', logs }, { status: 500 }));
            }
        });
    });
}
