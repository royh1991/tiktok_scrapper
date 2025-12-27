# AI Vacation Planner UI - Implementation Plan

## Goal
Build a professional, visually attractive React-based frontend (Next.js) for an AI-powered vacation planner. The app will act as a UI layer over existing Python scripts that search, download, and process TikTok videos for travel itineraries.

## User Review Required
> [!IMPORTANT]
> **Architecture**: The app will be built using **Next.js** to allow server-side execution of the local Python scripts via API routes.
> **Location**: The new project will be created in `/Users/rhu/projects/tiktok_scrapper/ui` to avoid modifying existing code.
> **Prerequisites**: The existing Python environment and dependencies must be available to the Next.js server (it will use the system `python3`).

## Proposed Architecture
- **Framework**: Next.js 14 (App Router)
- **Styling**: TailwindCSS
- **Animations**: Framer Motion
- **Backend Integration**: Next.js API Routes (`/api/...`) spawning Python subprocesses.

### Data Flow (Updated)
1.  **Search**: `POST /api/search` -> Accepts `tripId` AND `queryId`. Execs `tiktok_search.py` -> Output to `trips/[tripId]/[queryId]/urls.txt`.
2.  **Download**: `POST /api/download` -> Accepts `tripId` AND `queryId`. Execs `tiktok_downloader.py` -> Output to `trips/[tripId]/[queryId]/videos`.
3.  **Process**: `POST /api/process` -> Accepts `tripId` AND `queryId`. Execs `process.py` -> Output to `trips/[tripId]/[queryId]/videos`.
4.  **Results**: `GET /api/results` -> Accepts `tripId` AND `queryId`. Reads from `trips/[tripId]/[queryId]`.

## Proposed Changes

### [NEW] Frontend Application (`/ui`)

#### [NEW] Pages & Components
- **`app/page.tsx`**: Main entry point.
- **`components/TripDetails.tsx`**: [NEW] View showing all queries within a specific trip (e.g., "Food", "Shopping").
- **`components/QueryForm.tsx`**: [NEW] Modal to add a new search query to an existing trip.
- **`components/TripsDashboard.tsx`**: Updated to navigate to TripDetails instead of Results.

#### [NEW] Trips Architecture (Multi-Query)
- **Root**: `trips/[tripId]/`
  - `metadata.json` (Trip Title)
  - `[queryId]/` (Subfolder for each query)
    - `metadata.json` (Query string, status)
    - `urls.txt`
    - `videos/` (Processed content)

#### [NEW] API Routes (Updated)
- **`app/api/trips/route.ts`**: Handles creating Trips.
- **`app/api/queries/route.ts`**: [NEW] Handles creating Queries within a Trip.
- **`app/api/search/route.ts`**: Now requires `queryId`.
- **`app/api/download/route.ts`**: Now requires `queryId`.
- **`app/api/process/route.ts`**: Now requires `queryId`.


#### [NEW] Assets
- `public/splash-background.png`: Immersive, high-quality travel collage (custom generation).
- `public/search-hero.png`: Stylized 3D-style travel composition for the main search view.
- `public/loader-plane.png`: Cute isometric airplane character for the loading animation.
- `public/result-bg.png`: Subtle, premium map texture for the results dashboard background.

## Verification Plan

### Automated
- **Build Verification**: Run `npm run build` to ensure type safety and valid build.

### Manual Verification
- **Flow Test**:
    1.  Start app (`npm run dev`).
    2.  Verify Splash Screen appears.
    3.  Enter "Tokyo Itinerary" in Search.
    4.  Verify "Searching..." animation.
    5.  Verify "Downloading..." animation (simulated or real if fast enough).
    6.  Verify "Processing..." animation.
    7.  Check if results populate from the `output` folder.
