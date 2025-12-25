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

### Data Flow
1.  **Search**: `POST /api/search` -> Execs `tiktok_search.py`.
2.  **Download**: `POST /api/download` -> Execs `tiktok_downloader.py`.
3.  **Process**: `POST /api/process` -> Execs `process.py`.
4.  **Results**: `GET /api/results` -> Reads JSON/Media from `/output`.

## Proposed Changes

### [NEW] Frontend Application (`/ui`)
A new Next.js application will be initialized.

#### [NEW] Pages & Components
- **`app/page.tsx`**: Main entry point handling the flow logic (Wizard style state management).
- **`components/SplashScreen.tsx`**: Custom generated graphics, fades out on start.
- **`components/SearchForm.tsx`**: "Create a New Trip" style input.
- **`components/LoadingState.tsx`**: visually rich waiting screen with "cute" animations and status text.
- **`components/ResultsGrid.tsx`**: Masonry or grid layout for processed TikToks.
- **`components/VideoCard.tsx`**: Details component showing video, extracted text, and transcript.

#### [NEW] Trips Architecture
- **Root Directory**: All trip data is now nested under `/Users/rhu/projects/tiktok_scrapper/trips/[hash]`.
- **`metadata.json`**: Each trip folder contains details like title, query, and creation date.
- **Persistence**: The app scans the `/trips` directory on load to display existing planners.

#### [NEW] Enhanced Loading Experience
- **Granular Updates**: The UI now displays specific actions (e.g., "Downloading: 'Exploring Shinjuku' @tokyotraveller").
- **Dynamic Graphics**: Interactive animations triggered by the current step of the pipeline.

#### [NEW] Component Architecture (Expanded)
21. **`TripsDashboard`**: Grid of existing trip plans.
22. **`TripForm`**: Modal/View for creating a new trip with a title.
23. **`LiveStatus`**: Real-time ticker showing current video processing details.
24. **`ProgressBar`**: High-fidelity animated bar with estimated time remaining.

#### [NEW] API Routes (Updated)
- **`app/api/trips/route.ts`**: Handles listing and creating trip metadata.
- **`app/api/search/route.ts`**: Accepts `tripId`, saves results to trip folder.
- **`app/api/download/route.ts`**: Accepts `tripId`, pipes logs to frontend.
- **`app/api/process/route.ts`**: Accepts `tripId`.


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
