import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

export const dynamic = 'force-dynamic';

const PROJECT_ROOT = process.env.NEXT_PUBLIC_PROJECT_ROOT || '/Users/rhu/projects/tiktok_scrapper/';
const TRIPS_DIR = path.join(PROJECT_ROOT, 'trips');
// GET: List queries for a trip
export async function GET(req: Request) {
    const { searchParams } = new URL(req.url);
    const tripId = searchParams.get('tripId');

    if (!tripId) return NextResponse.json({ error: 'Trip ID required' }, { status: 400 });

    const tripPath = path.join(TRIPS_DIR, tripId);

    try {
        const entries = await fs.readdir(tripPath, { withFileTypes: true });

        const queries = await Promise.all(
            entries
                .filter(entry => entry.isDirectory() && entry.name !== 'videos')
                .map(async (dir) => {
                    const metaPath = path.join(tripPath, dir.name, 'metadata.json');
                    try {
                        const content = await fs.readFile(metaPath, 'utf-8');
                        return { id: dir.name, ...JSON.parse(content) };
                    } catch {
                        return { id: dir.name, query: dir.name, status: 'unknown', createdAt: new Date().toISOString() };
                    }
                })
        );

        // Sort by creation date DESC
        queries.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

        return NextResponse.json({ queries });
    } catch (error) {
        console.error('List queries error:', error);
        return NextResponse.json({ queries: [] }); // Return empty if trip doesn't exist or error
    }
}

export async function POST(req: Request) {
    try {
        const { tripId, query } = await req.json();

        if (!tripId) return NextResponse.json({ error: 'Trip ID required' }, { status: 400 });
        if (!query) return NextResponse.json({ error: 'Query required' }, { status: 400 });

        // Create a slug for the query
        const slug = query.toLowerCase().replace(/[^a-z0-9]/g, '-').substring(0, 30);
        const hash = Math.random().toString(36).substring(2, 6);
        const queryId = `${slug}-${hash}`;

        const queryPath = path.join(TRIPS_DIR, tripId, queryId);

        // Create query directory structure
        await fs.mkdir(queryPath, { recursive: true });
        await fs.mkdir(path.join(queryPath, 'videos'), { recursive: true });

        const metadata = {
            id: queryId,
            query,
            status: 'idle', // idle, searching, downloading, processing, complete
            createdAt: new Date().toISOString()
        };

        await fs.writeFile(
            path.join(queryPath, 'metadata.json'),
            JSON.stringify(metadata, null, 2)
        );

        return NextResponse.json({ success: true, queryId, metadata });

    } catch (error) {
        console.error('Create query error:', error);
        return NextResponse.json({ error: 'Failed to create query' }, { status: 500 });
    }
}
