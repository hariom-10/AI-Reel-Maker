# AI Reel Maker – Intelligent Local Video to Shorts Platform

AI Reel Maker is a modern, high-performance web platform that converts long videos (podcasts, lectures, interviews, gameplay, and vlogs) into multiple viral short-form vertical videos optimized for **Instagram Reels**, **YouTube Shorts**, and **Facebook Reels**.

Runs **100% locally on Windows** using **FastAPI**, **FFmpeg 8.1**, and a **React 19 + TypeScript + Vite + Tailwind CSS** frontend.

---

## Features

### 1. Dashboard
- Real-time statistics: Total Videos Uploaded, Total Clips Generated, Processing Videos, and Completed Projects.
- Recent Projects grid with thumbnails, duration badges, and direct links to open the studio.
- Quick action to upload a new video.

### 2. Large Video Upload
- Supports `MP4`, `MOV`, `MKV`, `WebM`, and `AVI`.
- Handles large videos (30 minutes, 1 hour, 2 hours, or more) streamed in chunks without exhausting RAM.
- Drag-and-drop zone with real-time percentage progress bar.
- Automatic metadata extraction: Duration, Resolution (e.g. 1080p, 4K), FPS, Bitrate, and File Size.
- In-modal video player to preview uploaded footage.

### 3. AI Multi-Modal Scene Detection
- Detects visual scene changes and cuts using FFmpeg scene heuristics and ContentDetector.
- Analyzes audio dynamics, speech volume peaks, and silence detection to locate high-energy dialogue moments.
- Assigns composite **Viral Engagement Scores** (0-100%) based on dialogue presence, pacing, and duration suitability.
- Generates high-resolution thumbnail previews for each moment.
- Filter scenes by: *All*, *High Speech*, *High Action*, or *Selected*.
- Select or reject candidate scenes before reel generation.

### 4. Automatic Reel Generator
- Configurable target durations:
  - **15 seconds**
  - **30 seconds**
  - **45 seconds**
  - **60 seconds**
  - **Custom duration** (5s - 120s)
- Select the exact number of reels to extract (e.g. 5, 10, or 15 clips).
- Intelligent boundary expansion aligns with natural pauses and scene transitions to prevent abrupt speech cuts.

### 5. Vertical Video Studio & Editor
- **Aspect Ratios**:
  - `9:16` (Instagram / TikTok / Shorts - 1080x1920)
  - `1:1` (Square Feed / LinkedIn - 1080x1080)
  - `16:9` (Standard Landscape - 1920x1080)
- **Framing & Composition Modes**:
  - `Smart Crop`: Subject-centered cropping with horizontal Pan (Center X slider 0% to 100%).
  - `Blurred Background Stack`: High-end dual-layer composite with blurred, darkened background behind the original video.
  - `Letterbox Fit`: Clean, distraction-free letterbox framing.
- **Trimming**: Live scrubbing range slider for Start Time and End Time with millisecond accuracy.
- **Creator Privacy Masking**: Blur personal regions (e.g. sensitive private numbers or dates on user's own footage) with configurable X, Y, Width, and Height sliders.

### 6. Automatic Captions & Subtitles
- Generates speech-aligned captions in:
  - **English**
  - **Hindi (हिंदी)**
  - **Hinglish**
- High-visibility styling presets:
  - **Bold Outline** (Hormozi / MrBeast viral shorts aesthetic)
  - **Clean Pill** (Dark background box)
  - **Karaoke** (Dynamic highlights)
  - **Classic**
- Customization:
  - Font families: Impact, Montserrat, Arial Bold, Roboto.
  - Font size slider (16px - 44px).
  - Vibrant color presets: Viral Gold (`#FFD700`), Pure White, Neon Cyan, Lime Green, Hot Pink.
  - Vertical alignment: Bottom, Center, Top, or Custom Y position.
- Inline caption line editor to tweak text and timestamps.
- One-click toggle to enable or disable subtitles.

### 7. Batch Export & ZIP Download
- Export multiple clips simultaneously.
- High-quality H.264 MP4 output at 30 FPS and 1080x1920 resolution.
- Individual progress tracking with Completed, Rendering, and Retry states.
- One-click **Download All (ZIP)** button bundling all completed reels.

### 8. Project Persistence
- Projects, metadata, thumbnails, and exported reels are saved locally under `backend/data/`.
- Projects persist across browser refreshes and backend restarts.
- Rename or delete projects anytime from the "My Projects" view.

---

## Getting Started

### Quick Start (Double-Click on Windows)
Simply double-click:
```
start.bat
```
This automatically launches the FastAPI backend on port 8000, starts the Vite frontend on port 5173, and opens your default browser at `http://localhost:5173`.

### Or Run via Terminal:

1. **Start the Backend**:
```powershell
python run_backend.py
```
*(Backend runs at `http://127.0.0.1:8000` with interactive API docs at `http://127.0.0.1:8000/docs`)*

2. **Start the Frontend**:
```powershell
cd frontend
npm run dev
```
*(Frontend runs at `http://localhost:5173`)*

---

## Directory Structure

```
AI reel maker/
├── backend/
│   ├── app.py                 # FastAPI endpoints & static media streaming
│   ├── config.py              # Storage paths and system configuration
│   ├── models.py              # Pydantic schemas (Projects, Clips, Captions)
│   ├── services/
│   │   ├── video_analyzer.py  # Scene detection, speech density, and viral scoring
│   │   ├── reel_generator.py  # Clip segmentation and candidate ranking
│   │   ├── video_editor.py    # FFmpeg 9:16 rendering, blur stack & ASS subtitle burn
│   │   ├── transcriber.py     # Subtitle generation, language presets & ASS styling
│   │   └── project_store.py   # Local JSON persistence
│   └── data/                  # Local storage (uploads, exports, thumbnails, projects)
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # Main application layout and state manager
│   │   ├── types.ts           # TypeScript interfaces
│   │   ├── services/api.ts    # Fetch API client with upload progress
│   │   └── components/
│   │       ├── Sidebar.tsx            # Navigation sidebar
│   │       ├── Header.tsx             # Top header bar
│   │       ├── DashboardView.tsx      # Analytics & recent projects
│   │       ├── UploadModal.tsx        # Drag & drop upload & video probe preview
│   │       ├── SceneInspector.tsx     # AI moments viewer & score filter
│   │       ├── StudioView.tsx         # Interactive vertical 9:16 editor
│   │       ├── ReelGeneratorModal.tsx # Duration & clip count configuration
│   │       ├── BatchExportModal.tsx   # Multi-clip render & ZIP download
│   │       ├── ProjectsView.tsx       # Local project management
│   │       ├── VideoLibraryView.tsx   # Unified media gallery
│   │       ├── SettingsView.tsx       # System parameters & cache cleaner
│   │       └── VideoPreviewModal.tsx  # Fullscreen video playback modal
│   ├── vite.config.ts         # Vite configuration with Tailwind CSS v4 & proxy
│   └── package.json
│
├── start.bat                  # One-click Windows batch launcher
├── start.ps1                  # PowerShell launcher
├── run_backend.py             # Python server runner
└── test_workflow.py           # Automated end-to-end integration test
```

---

## System Requirements
- **OS**: Windows 10 / 11
- **Python**: 3.10+ (tested on Python 3.14)
- **Node.js**: v18+ (tested on Node v25.9)
- **FFmpeg**: Installed and available in PATH (tested with FFmpeg 8.1)
