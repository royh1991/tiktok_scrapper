import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const PROJECT_ROOT = process.env.NEXT_PUBLIC_PROJECT_ROOT || '/Users/rhu/projects/tiktok_scrapper/';
const TRIPS_DIR = path.join(PROJECT_ROOT, 'trips');

// GET: List all trips
export async function GET() {
    try {
        await fs.mkdir(TRIPS_DIR, { recursive: true });
        const entries = await fs.readdir(TRIPS_DIR, { withFileTypes: true });

        const trips = await Promise.all(
            entries
                .filter(entry => entry.isDirectory())
                .map(async (dir) => {
                    const metaPath = path.join(TRIPS_DIR, dir.name, 'metadata.json');
                    try {
                        const content = await fs.readFile(metaPath, 'utf-8');
                        return { id: dir.name, ...JSON.parse(content) };
                    } catch {
                        return { id: dir.name, title: dir.name, status: 'unknown' };
                    }
                })
        );

        return NextResponse.json({ trips });
    } catch (error) {
        console.error('List trips error:', error);
        return NextResponse.json({ error: 'Failed to list trips' }, { status: 500 });
    }
}

// POST: Create a new trip
export async function POST(req: Request) {
    try {
        const { title, query } = await req.json();
        if (!title) return NextResponse.json({ error: 'Title required' }, { status: 400 });

        const slug = title.toLowerCase().replace(/[^a-z0-9]/g, '-').substring(0, 20);
        const hash = Math.random().toString(36).substring(2, 6);
        const tripId = `${slug}-${hash}`;
        const tripPath = path.join(TRIPS_DIR, tripId);

        await fs.mkdir(tripPath, { recursive: true });

        // Removed the incorrect creation of 'videos' directory at the trip level
        // await fs.mkdir(path.join(tripPath, 'videos'), { recursive: true });

        const metadata = {
            title,
            query: query || '',
            status: 'idle',
            createdAt: new Date().toISOString()
        };

        await fs.writeFile(
            path.join(tripPath, 'metadata.json'),
            JSON.stringify(metadata, null, 2)
        );

        return NextResponse.json({ success: true, tripId, metadata });
    } catch (error) {
        console.error('Create trip error:', error);
        return NextResponse.json({ error: 'Failed to create trip' }, { status: 500 });
    }
}
