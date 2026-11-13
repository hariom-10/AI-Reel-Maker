import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import aiofiles

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import UPLOADS_DIR, THUMBNAILS_DIR, EXPORTS_DIR, ALLOWED_EXTENSIONS
from models import (
    Project, VideoMetadata, DetectedScene, ClipConfig,
    GenerateReelsRequest, ExportRequest, RenameProjectRequest
)
from services.project_store import project_store
from services.video_analyzer import probe_video, extract_thumbnail, analyze_video_scenes
from services.reel_generator import generate_automatic_reels
from services.video_editor import render_clip, create_export_zip

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Reel Maker API",
    description="Intelligent Local Video to Shorts / Reels Platform",
    version="1.0.0"
)

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local media directories for static video/image streaming
app.mount("/media/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/media/thumbnails", StaticFiles(directory=str(THUMBNAILS_DIR)), name="thumbnails")
app.mount("/media/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")

# Background job runners
def run_background_analysis(project_id: str):
    """Executes multi-modal scene analysis in background."""
    project = project_store.get_project(project_id)
    if not project:
        return

    try:
        project.status = "analyzing"
        project.progress = 5
        project.status_message = "Starting video analysis..."
        project_store.save_project(project)

        def progress_cb(pct: int, msg: str):
            project.progress = pct
            project.status_message = msg
            project_store.save_project(project)

        video_path = Path(project.video_path)
        scenes = analyze_video_scenes(video_path, project.id, progress_callback=progress_cb)

        project.scenes = scenes
        project.status = "ready"
        project.progress = 100
        project.status_message = f"Analysis complete. {len(scenes)} scenes detected."
        project_store.save_project(project)
    except Exception as e:
        logger.error(f"Analysis failed for {project_id}: {e}")
        project.status = "ready"
        project.status_message = f"Analysis error: {str(e)}"
        project_store.save_project(project)

def run_background_export(project_id: str, clip_ids: List[str]):
    """Renders multiple reel clips in background and builds ZIP archive."""
    project = project_store.get_project(project_id)
    if not project:
        return

    try:
        project.status = "exporting"
        project.progress = 10
        project.status_message = "Preparing batch export..."
        project_store.save_project(project)

        video_path = Path(project.video_path)
        total_clips = len(clip_ids)
        rendered_count = 0

        for clip in project.clips:
            if clip.clip_id in clip_ids:
                clip.status = "rendering"
                project_store.save_project(project)

                def clip_progress(pct: int, msg: str):
                    overall = int(10 + ((rendered_count + (pct / 100.0)) / total_clips) * 80)
                    project.progress = overall
                    project.status_message = msg
                    project_store.save_project(project)

                render_clip(video_path, clip, project.id, progress_callback=clip_progress)
                rendered_count += 1
                project_store.save_project(project)

        # Build ZIP bundle
        zip_url = create_export_zip(project.id, project.clips)

        project.status = "completed"
        project.progress = 100
        project.status_message = f"Batch export finished. {rendered_count} clips ready."
        project_store.save_project(project)
    except Exception as e:
        logger.error(f"Batch export failed for {project_id}: {e}")
        project.status = "completed"
        project.status_message = f"Export finished with notice: {str(e)}"
        project_store.save_project(project)

# ----------------- Routes ----------------- #

@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/stats")
def get_dashboard_stats():
    """Returns dashboard metric counts and recent projects."""
    return project_store.get_stats()

@app.get("/api/projects")
def list_projects():
    """List all saved projects."""
    return project_store.list_projects()

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    """Retrieve full project details."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj

@app.patch("/api/projects/{project_id}")
def rename_project(project_id: str, payload: RenameProjectRequest):
    """Rename project."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    proj.name = payload.name
    return project_store.save_project(proj)

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    """Delete project and associated files."""
    success = project_store.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True, "message": "Project deleted successfully"}

@app.post("/api/upload")
async def upload_video(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None)
):
    """
    Safely stream and save large video uploads without loading entire file into RAM.
    Probes technical metadata and extracts opening thumbnail.
    """
    filename = file.filename or "video.mp4"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format: '{ext}'. Supported formats: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    project_id = str(uuid.uuid4())[:12]
    saved_filename = f"{project_id}_{filename}"
    saved_path = UPLOADS_DIR / saved_filename

    # Stream file to disk in 1MB chunks
    try:
        async with aiofiles.open(saved_path, "wb") as out_file:
            while content := await file.read(1024 * 1024):
                await out_file.write(content)
    except Exception as e:
        logger.error(f"Error saving upload: {e}")
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(status_code=500, detail="Failed to save video file")

    # Probe metadata
    metadata = probe_video(saved_path)

    # Initial thumbnail
    thumb_name = f"{project_id}_cover.jpg"
    thumb_path = THUMBNAILS_DIR / thumb_name
    extract_thumbnail(saved_path, min(2.0, metadata.duration / 2), thumb_path)

    proj_name = name if name and name.strip() else Path(filename).stem.replace("_", " ").title()

    new_project = Project(
        id=project_id,
        name=proj_name,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        video_filename=filename,
        video_path=str(saved_path),
        video_url=f"/media/uploads/{saved_filename}",
        metadata=metadata,
        scenes=[],
        clips=[],
        status="uploaded",
        progress=0,
        status_message="Video uploaded successfully"
    )

    saved_proj = project_store.save_project(new_project)
    return saved_proj

@app.post("/api/projects/{project_id}/analyze")
def trigger_analysis(project_id: str, background_tasks: BackgroundTasks):
    """Triggers multi-modal AI scene detection and moment ranking."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    proj.status = "analyzing"
    proj.progress = 5
    proj.status_message = "Initiating multi-modal scene analysis..."
    project_store.save_project(proj)

    background_tasks.add_task(run_background_analysis, project_id)
    return {"success": True, "message": "Analysis started in background", "project": proj}

@app.post("/api/projects/{project_id}/generate-reels")
def generate_reels(project_id: str, req: GenerateReelsRequest):
    """Generates configured candidate reels from detected scenes."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    # If scenes are not yet detected, generate scenes first
    if not proj.scenes:
        video_path = Path(proj.video_path)
        proj.scenes = analyze_video_scenes(video_path, proj.id)

    video_path = Path(proj.video_path)
    clips = generate_automatic_reels(
        scenes=proj.scenes,
        video_duration=proj.metadata.duration,
        video_path=video_path,
        project_id=proj.id,
        target_count=req.target_count,
        target_duration=req.clip_duration,
        aspect_ratio=req.aspect_ratio,
        mode=req.mode,
        auto_captions=req.auto_captions,
        caption_language=req.caption_language,
        caption_style=req.caption_style
    )

    proj.clips = clips
    proj.status = "ready"
    proj.status_message = f"Generated {len(clips)} candidate reels ready for preview and editing."
    project_store.save_project(proj)

    return proj

@app.put("/api/projects/{project_id}/clips/{clip_id}")
def update_clip(project_id: str, clip_id: str, updated_clip: ClipConfig):
    """Update a clip's trim timing, aspect ratio, crop config, or subtitles."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    for i, clip in enumerate(proj.clips):
        if clip.clip_id == clip_id:
            # Recompute duration
            updated_clip.duration = round(updated_clip.end_time - updated_clip.start_time, 2)
            # Reset export status if timing or crop changed
            if (clip.start_time != updated_clip.start_time or 
                clip.end_time != updated_clip.end_time or 
                clip.crop_config != updated_clip.crop_config or
                clip.caption_config != updated_clip.caption_config):
                updated_clip.status = "ready"
                updated_clip.output_url = ""
            proj.clips[i] = updated_clip
            project_store.save_project(proj)
            return updated_clip

    raise HTTPException(status_code=404, detail="Clip not found in project")

@app.post("/api/projects/{project_id}/clips/{clip_id}/render")
def render_single_clip(project_id: str, clip_id: str):
    """Renders a single vertical clip immediately."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    target_clip = next((c for c in proj.clips if c.clip_id == clip_id), None)
    if not target_clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    video_path = Path(proj.video_path)
    rendered = render_clip(video_path, target_clip, proj.id)

    # Save project state
    for i, c in enumerate(proj.clips):
        if c.clip_id == clip_id:
            proj.clips[i] = rendered
            break
    project_store.save_project(proj)

    return rendered

@app.post("/api/projects/{project_id}/export-batch")
def export_batch(project_id: str, req: ExportRequest, background_tasks: BackgroundTasks):
    """Batch export multiple clips with progress tracking."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    if not req.clip_ids:
        raise HTTPException(status_code=400, detail="No clip IDs provided for export")

    background_tasks.add_task(run_background_export, project_id, req.clip_ids)
    return {"success": True, "message": f"Exporting {len(req.clip_ids)} clips in background"}

@app.get("/api/projects/{project_id}/download-all")
def get_all_reels_download(project_id: str):
    """Returns the URL of the downloadable ZIP containing all completed clips."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    zip_url = create_export_zip(proj.id, proj.clips)
    if not zip_url:
        raise HTTPException(status_code=404, detail="No exported clips available to download")

    return {"download_url": zip_url}
