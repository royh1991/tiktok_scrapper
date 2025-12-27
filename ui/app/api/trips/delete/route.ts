import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const PROJECT_ROOT = process.env.NEXT_PUBLIC_PROJECT_ROOT || '';

export async function DELETE(req: Request) {
    try {
        const { searchParams } = new URL(req.url);
        const tripId = searchParams.get('tripId');

        if (!tripId) {
            return NextResponse.json({ error: 'tripId is required' }, { status: 400 });
        }

        const tripPath = path.join(PROJECT_ROOT, 'trips', tripId);

        // Recursive deletion
        await fs.rm(tripPath, { recursive: true, force: true });

        return NextResponse.json({ success: true, message: `Trip ${tripId} deleted successfully` });
    } catch (error: any) {
        console.error('Delete Trip Error:', error);
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
