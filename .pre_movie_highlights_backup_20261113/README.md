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

### 3. Scene Detection & Moment Ranking
- Detects visual scene changes using PySceneDetect when installed, with an FFmpeg fallback.
- Uses audio activity, scene pacing, and duration heuristics to rank candidate moments. Scores are suggestions, not a guarantee of engagement.
- Generates high-resolution thumbnail previews for each moment.
- Filter scenes by: *All*, *High Audio Activity*, *High Action*, or *Selected*.
- Select or reject candidate scenes before reel generation.

### 4. Reel Candidate Generator
- Configurable target durations:
  - **15 seconds**
  - **30 seconds**
  - **45 seconds**
  - **60 seconds**
  - **Custom duration** (5s - 120s)
- Request up to 30 reels; candidates are selected only from the chosen scenes. If the selected scenes do not contain enough separated moments, fewer clips are produced.
- Windows are aligned to scene boundaries where possible. Dialogue-aware cut points are not guaranteed.

### 5. Vertical Video Studio & Editor
- **Aspect Ratios**:
  - `9:16` (Instagram / TikTok / Shorts - 1080x1920)
  - `1:1` (Square Feed / LinkedIn - 1080x1080)
  - `16:9` (Standard Landscape - 1920x1080)
- **Framing & Composition Modes**:
  - `Smart Crop`: Centered crop with horizontal pan control.
  - `Blurred Background Stack`: High-end dual-layer composite with blurred, darkened background behind the original video.
  - `Letterbox Fit`: Clean, distraction-free letterbox framing.
- **Trimming**: Live scrubbing range slider for Start Time and End Time with millisecond accuracy.
- **Creator Privacy Masking**: Blur personal regions (e.g. sensitive private numbers or dates on user's own footage) with configurable X, Y, Width, and Height sliders.

### 6. Automatic Captions & Subtitles
- Uses local Whisper transcription for English and Hindi when the optional Whisper package and model are installed. Hinglish uses Whisper language detection; mixed-language accuracy varies.
- Without Whisper, captions are omitted rather than replaced with sample or fabricated dialogue.
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

### 8. Authorized Video Region Editor
- Requires an ownership/permission confirmation for both preview and export.
- Supports spatial delogo, blur, text overlay, and delogo with replacement text. Region boxes can be dragged and adjusted.
- Uses FFmpeg's spatial delogo filter, not AI video inpainting or motion tracking. Review the preview; moving overlays may not be removed cleanly.
- Leaves the source video untouched and writes a separate edited file.

### 9. Project Persistence
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

### Python dependencies and optional captions

Install the backend dependencies from the repository root:
```powershell
python -m pip install -r requirements.txt
```
FFmpeg and FFprobe must also be installed and available on `PATH`.

Whisper is optional because it downloads a model and requires PyTorch. To enable actual local speech captions:
```powershell
python -m pip install -r requirements-whisper.txt
```
The first caption run downloads Whisper's `base` model. Video and audio are processed locally; with Whisper absent or unavailable, caption generation reports that it was skipped and does not invent text.

Generate a synthetic starter project, without replacing an existing demo by default:
```powershell
python create_sample_project.py
```
Use `--overwrite` only when you intend to replace the existing starter video and project.

---

## Directory Structure

```
AI reel maker/
├── backend/
│   ├── app.py                 # FastAPI endpoints & static media streaming
│   ├── config.py              # Storage paths and system configuration
│   ├── models.py              # Pydantic schemas (Projects, Clips, Captions)
│   ├── services/
│   │   ├── video_analyzer.py  # Scene detection and audio-activity ranking
│   │   ├── reel_generator.py  # Clip segmentation and candidate ranking
│   │   ├── video_editor.py    # FFmpeg 9:16 rendering, blur stack & ASS subtitle burn
│   │   ├── transcriber.py     # Optional Whisper transcription and ASS styling
│   │   ├── video_cleanup.py   # Authorized FFmpeg region edits
│   │   ├── ffmpeg_runner.py   # FFmpeg progress and cancellation
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
│   │       ├── VideoPreviewModal.tsx  # Fullscreen video playback modal
│   │       └── VideoCleanupView.tsx   # Authorized cleanup editor and preview
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
- **Python**: 3.10+
- **Node.js**: v20.19+ or v22.12+ (tested on Node v25.9)
- **FFmpeg**: Installed and available in PATH (tested with FFmpeg 8.1)

## Current processing limits

- Scene selection uses visual cuts and audio-activity heuristics; semantic dialogue understanding and engagement prediction are not provided.
- Automatic captions require optional local Whisper installation and model download.
- Smart crop is a centered crop with manual horizontal adjustment; face-aware tracking is not implemented.
- Cleanup is a spatial FFmpeg approximation. It does not reconstruct missing content with a generative model or track moving marks.
- Generated clip count can be lower than requested when the selected moments overlap or are too short.
