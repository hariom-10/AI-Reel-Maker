import uuid
import logging
import math
from pathlib import PureWindowsPath
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set
import aiofiles

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    EXPORTS_DIR,
    THUMBNAILS_DIR,
    UPLOADS_DIR,
)
from models import (
    Project, VideoMetadata, DetectedScene, ClipConfig, CleanupRegion,
    GenerateReelsRequest, ExportRequest, CleanupRequest, CleanupRegionsRequest,
    RenameProjectRequest
)
from services.project_store import project_store
from services.video_analyzer import probe_video, extract_thumbnail, analyze_video_scenes
from services.reel_generator import generate_automatic_reels
from services.video_editor import render_clip, create_export_zip
from services.video_cleanup import render_cleanup_video, render_cleanup_preview_frame
from services.transcriber import whisper_available

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Reel Maker Pro API",
    description="Intelligent Local Video to Shorts / Reels & Cleanup Platform",
    version="2.0.0"
)

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai-reel-maker-six.vercel.app"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local media directories for static video/image streaming
app.mount("/media/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/media/thumbnails", StaticFiles(directory=str(THUMBNAILS_DIR)), name="thumbnails")
app.mount("/media/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")

# Job cancellation registry
cancelled_jobs: Set[str] = set()

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
            if project_id in cancelled_jobs:
                raise InterruptedError("Cancelled by user")
            project.progress = pct
            project.status_message = msg
            project_store.save_project(project)

        video_path = Path(project.video_path)
        scenes = analyze_video_scenes(video_path, project.id, progress_callback=progress_cb)

        if project_id in cancelled_jobs:
            cancelled_jobs.discard(project_id)
            project.status = "ready"
            project.status_message = "Analysis cancelled."
            project_store.save_project(project)
            return

        project.scenes = scenes
        project.status = "ready"
        project.progress = 100
        project.status_message = f"Analysis complete. {len(scenes)} scenes detected."
        project_store.save_project(project)
    except InterruptedError:
        logger.info(f"Analysis for {project_id} cancelled.")
        cancelled_jobs.discard(project_id)
        project.status = "ready"
        project.status_message = "Analysis cancelled by user."
        project_store.save_project(project)
    except Exception as e:
        cancelled_jobs.discard(project_id)
        logger.error(f"Analysis failed for {project_id}: {e}")
        project.status = "ready"
        project.status_message = f"Analysis error: {str(e)}"
        project_store.save_project(project)


def run_background_generation(project_id: str, req: GenerateReelsRequest):
    """Analyze selected moments and prepare reel candidates without blocking the API."""
    project = project_store.get_project(project_id)
    if not project:
        return

    try:
        project.status = "generating"
        project.progress = 5
        project.status_message = "Preparing selected reel candidates..."
        project_store.save_project(project)

        def progress_cb(percent: int, message: str):
            if project_id in cancelled_jobs:
                raise InterruptedError("Cancelled by user")
            project.progress = min(99, max(5, percent))
            project.status_message = message
            project_store.save_project(project)

        video_path = Path(project.video_path)
        if not project.scenes:
            project.scenes = analyze_video_scenes(
                video_path,
                project.id,
                progress_callback=lambda percent, message: progress_cb(
                    5 + int(percent * 0.3), message
                ),
            )

        selected_scenes = [scene for scene in project.scenes if scene.selected]
        if not selected_scenes:
            project.status = "ready"
            project.progress = 100
            project.status_message = "Select at least one scene before generating reels."
            project_store.save_project(project)
            return

        clips = generate_automatic_reels(
            scenes=selected_scenes,
            video_duration=project.metadata.duration,
            video_path=video_path,
            project_id=project.id,
            target_count=req.target_count,
            target_duration=req.clip_duration,
            aspect_ratio=req.aspect_ratio,
            mode=req.mode,
            auto_captions=req.auto_captions,
            caption_language=req.caption_language,
            caption_style=req.caption_style,
            progress_callback=lambda percent, message: progress_cb(
                35 + int(percent * 0.64), message
            ),
        )
        if project_id in cancelled_jobs:
            raise InterruptedError("Cancelled by user")
        if not clips:
            project.status = "ready"
            project.progress = 100
            project.status_message = (
                "No separated reel candidates fit the selected scenes and duration. "
                "Select more scenes or choose a shorter duration."
            )
            project_store.save_project(project)
            return

        project.clips = clips
        project.status = "ready"
        project.progress = 100
        project.status_message = (
            f"Generated {len(clips)} candidate reels ready for preview and editing."
        )
        if req.auto_captions and not whisper_available():
            project.status_message += (
                " Captions were skipped; install optional openai-whisper to enable transcription."
            )
        elif req.auto_captions and any(not clip.subtitles for clip in clips):
            project.status_message += " Some clips have no detected speech captions."
        project_store.save_project(project)
    except InterruptedError:
        cancelled_jobs.discard(project_id)
        project.status = "ready"
        project.status_message = "Reel generation cancelled."
        project_store.save_project(project)
    except Exception as exc:
        cancelled_jobs.discard(project_id)
        logger.exception("Reel generation failed for %s", project_id)
        project.status = "ready"
        project.status_message = f"Reel generation failed: {exc}"
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
            if project_id in cancelled_jobs:
                cancelled_jobs.remove(project_id)
                project.status = "completed" if rendered_count > 0 else "ready"
                project.status_message = f"Export halted by user. {rendered_count} clips finished."
                project_store.save_project(project)
                return

            if clip.clip_id in clip_ids:
                clip.status = "rendering"
                project_store.save_project(project)

                def clip_progress(pct: int, msg: str):
                    if project_id in cancelled_jobs:
                        raise InterruptedError("Cancelled by user")
                    overall = int(10 + ((rendered_count + (pct / 100.0)) / total_clips) * 80)
                    project.progress = overall
                    project.status_message = msg
                    project_store.save_project(project)

                render_clip(video_path, clip, project.id, progress_callback=clip_progress)
                rendered_count += 1
                project_store.save_project(project)

        # Build ZIP bundle
        create_export_zip(project.id, project.clips)
        failed_count = sum(1 for clip in project.clips if clip.clip_id in clip_ids and clip.status == "error")
        rendered_count = sum(1 for clip in project.clips if clip.clip_id in clip_ids and clip.status == "exported")

        project.status = "completed"
        project.progress = 100
        project.status_message = (
            f"Batch export finished: {rendered_count}/{total_clips} clips ready."
            + (f" {failed_count} failed; retry them from the editor." if failed_count else "")
        )
        project_store.save_project(project)
    except InterruptedError:
        cancelled_jobs.discard(project_id)
        project.status = "completed" if any(c.status == "exported" for c in project.clips) else "ready"
        project.status_message = "Export cancelled. Completed clips were kept."
        project_store.save_project(project)
    except Exception as e:
        cancelled_jobs.discard(project_id)
        logger.error(f"Batch export failed for {project_id}: {e}")
        project.status = "ready"
        project.status_message = f"Export failed: {str(e)}"
        project_store.save_project(project)

def run_background_cleanup(project_id: str, regions: List[CleanupRegion]):
    """Processes authorized spatial region edits in the background."""
    project = project_store.get_project(project_id)
    if not project:
        return

    try:
        project.status = "cleaning"
        project.progress = 10
        project.status_message = "Starting authorized region cleanup..."
        project_store.save_project(project)

        def cleanup_cb(pct: int, msg: str):
            if project_id in cancelled_jobs:
                raise InterruptedError("Cancelled by user")
            project.progress = pct
            project.status_message = msg
            project_store.save_project(project)

        video_path = Path(project.video_path)
        out_path = render_cleanup_video(
            video_path=video_path,
            regions=regions,
            project_id=project.id,
            metadata=project.metadata,
            progress_callback=cleanup_cb
        )

        if project_id in cancelled_jobs:
            cancelled_jobs.remove(project_id)
            project.status = "ready"
            project.status_message = "Cleanup cancelled by user."
            project_store.save_project(project)
            return

        if out_path and out_path.exists():
            project.cleaned_video_path = str(out_path)
            project.cleaned_video_url = f"/media/exports/{out_path.name}"
            project.cleanup_regions = regions
            project.status = "ready"
            project.progress = 100
            project.status_message = "Region cleanup finished successfully."
        else:
            project.status = "ready"
            project.status_message = "Cleanup failed: FFmpeg did not produce an edited file."

        project_store.save_project(project)
    except InterruptedError:
        cancelled_jobs.discard(project_id)
        project.status = "ready"
        project.status_message = "Cleanup cancelled by user."
        project_store.save_project(project)
    except Exception as e:
        cancelled_jobs.discard(project_id)
        logger.error(f"Cleanup failed for {project_id}: {e}")
        project.status = "ready"
        project.status_message = f"Cleanup failed: {str(e)}"
        project_store.save_project(project)

# ----------------- Routes ----------------- #

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "features": {"whisper": whisper_available()},
    }

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
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status in {"analyzing", "generating", "cleaning", "exporting"}:
        raise HTTPException(status_code=409, detail="Cancel the active processing job before deleting this project.")
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
    raw_filename = (file.filename or "video.mp4").replace("/", "\\")
    filename = PureWindowsPath(raw_filename).name or "video.mp4"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format: '{ext}'. Supported formats: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    project_id = str(uuid.uuid4())[:12]
    saved_filename = f"{project_id}{ext}"
    saved_path = UPLOADS_DIR / saved_filename

    # Stream file to disk in 1MB chunks
    try:
        if file.size is not None and file.size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="Video exceeds the 50 GB upload limit.")
        async with aiofiles.open(saved_path, "wb") as out_file:
            bytes_written = 0
            while content := await file.read(1024 * 1024):
                bytes_written += len(content)
                if bytes_written > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail="Video exceeds the 50 GB upload limit.")
                await out_file.write(content)
        metadata = probe_video(saved_path)
    except HTTPException:
        saved_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        logger.exception("Could not save or validate uploaded video.")
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Upload is not a valid, readable video.") from e
    finally:
        await file.close()

    # Initial thumbnail
    thumb_name = f"{project_id}_cover.jpg"
    thumb_path = THUMBNAILS_DIR / thumb_name
    extract_thumbnail(saved_path, min(2.0, metadata.duration / 2), thumb_path)

    proj_name = (name.strip()[:120] if name and name.strip()
                 else Path(filename).stem.replace("_", " ").title())

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
    if proj.status in {"analyzing", "generating", "cleaning", "exporting"}:
        raise HTTPException(status_code=409, detail="This project already has an active processing job.")

    proj.status = "analyzing"
    cancelled_jobs.discard(project_id)
    proj.progress = 5
    proj.status_message = "Initiating multi-modal scene analysis..."
    project_store.save_project(proj)

    background_tasks.add_task(run_background_analysis, project_id)
    return {"success": True, "message": "Analysis started in background", "project": proj}

@app.post("/api/projects/{project_id}/generate-reels")
def generate_reels(
    project_id: str,
    req: GenerateReelsRequest,
    background_tasks: BackgroundTasks,
):
    """Starts reel candidate selection and optional transcription in the background."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.status in {"analyzing", "generating", "cleaning", "exporting"}:
        raise HTTPException(status_code=409, detail="This project already has an active processing job.")
    cancelled_jobs.discard(project_id)
    proj.status = "generating"
    proj.progress = 0
    proj.status_message = "Preparing selected reel candidates..."
    project_store.save_project(proj)
    background_tasks.add_task(run_background_generation, project_id, req)

    return {
        "success": True,
        "message": "Reel generation started in the background.",
        "project": proj,
    }

@app.put("/api/projects/{project_id}/clips/{clip_id}")
def update_clip(project_id: str, clip_id: str, updated_clip: ClipConfig):
    """Update a clip's trim timing, aspect ratio, crop config, or subtitles."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.status in {"analyzing", "generating", "cleaning", "exporting"}:
        raise HTTPException(status_code=409, detail="This project already has an active processing job.")

    for i, clip in enumerate(proj.clips):
        if clip.clip_id == clip_id:
            if (
                updated_clip.start_time < 0
                or updated_clip.end_time <= updated_clip.start_time
                or updated_clip.end_time > proj.metadata.duration
            ):
                raise HTTPException(status_code=422, detail="Clip trim points are outside the source video.")
            updated_clip.clip_id = clip_id
            updated_clip.duration = round(updated_clip.end_time - updated_clip.start_time, 2)
            has_render_changes = (
                clip.start_time != updated_clip.start_time
                or clip.end_time != updated_clip.end_time
                or clip.crop_config != updated_clip.crop_config
                or clip.caption_config != updated_clip.caption_config
                or clip.subtitles != updated_clip.subtitles
            )
            updated_clip.output_path = "" if has_render_changes else clip.output_path
            updated_clip.output_url = "" if has_render_changes else clip.output_url
            updated_clip.error_message = "" if has_render_changes else clip.error_message
            if has_render_changes:
                updated_clip.status = "ready"
            else:
                updated_clip.status = clip.status
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
    if proj.status in {"analyzing", "generating", "cleaning", "exporting"}:
        raise HTTPException(status_code=409, detail="This project already has an active processing job.")

    target_clip = next((c for c in proj.clips if c.clip_id == clip_id), None)
    if not target_clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    video_path = Path(proj.video_path)
    rendered = render_clip(video_path, target_clip, proj.id)

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
    if proj.status in {"analyzing", "generating", "cleaning", "exporting"}:
        raise HTTPException(status_code=409, detail="This project already has an active processing job.")

    if not req.clip_ids:
        raise HTTPException(status_code=400, detail="No clip IDs provided for export")
    existing_clip_ids = {clip.clip_id for clip in proj.clips}
    if len(set(req.clip_ids)) != len(req.clip_ids) or not set(req.clip_ids) <= existing_clip_ids:
        raise HTTPException(status_code=400, detail="One or more clip IDs are invalid.")

    cancelled_jobs.discard(project_id)
    proj.status = "exporting"
    proj.progress = 0
    proj.status_message = "Preparing batch export..."
    project_store.save_project(proj)
    background_tasks.add_task(run_background_export, project_id, req.clip_ids)
    return {"success": True, "message": f"Exporting {len(req.clip_ids)} clips in background"}

@app.get("/api/projects/{project_id}/download-all")
def get_all_reels_download(project_id: str):
    """Returns the URL of the downloadable ZIP containing all completed clips."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.status in {"analyzing", "generating", "cleaning", "exporting"}:
        raise HTTPException(status_code=409, detail="This project already has an active processing job.")

    zip_url = create_export_zip(proj.id, proj.clips)
    if not zip_url:
        raise HTTPException(status_code=404, detail="No exported clips available to download")

    return {"download_url": zip_url}

# ----------------- AI Video Cleanup Endpoints ----------------- #

@app.put("/api/projects/{project_id}/cleanup-regions")
def save_cleanup_regions(project_id: str, req: CleanupRegionsRequest):
    """Persist cleanup editor settings without applying them to the source video."""
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status in {"analyzing", "generating", "cleaning", "exporting"}:
        raise HTTPException(status_code=409, detail="Wait for the active processing job before editing cleanup regions.")

    project.cleanup_regions = req.regions
    project_store.save_project(project)
    return {"regions": project.cleanup_regions}

@app.post("/api/projects/{project_id}/cleanup")
def trigger_video_cleanup(
    project_id: str,
    req: CleanupRequest,
    background_tasks: BackgroundTasks
):
    """
    Applies authorized spatial region edits using FFmpeg.
    Mandates ownership authorization confirmation.
    Original video file remains completely untouched.
    """
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.status in {"analyzing", "generating", "cleaning", "exporting"}:
        raise HTTPException(status_code=409, detail="This project already has an active processing job.")

    if not req.authorization_confirmed:
        raise HTTPException(
            status_code=403,
            detail="Authorization confirmation required. You must confirm ownership or permission to edit this video."
        )

    if not req.regions:
        raise HTTPException(status_code=400, detail="At least one cleanup region must be specified.")

    cancelled_jobs.discard(project_id)
    proj.status = "cleaning"
    proj.progress = 5
    proj.status_message = "Starting authorized region edit..."
    project_store.save_project(proj)

    background_tasks.add_task(run_background_cleanup, project_id, req.regions)
    return {"success": True, "message": "Video cleanup started in background", "project": proj}

@app.post("/api/projects/{project_id}/cleanup/preview")
def preview_cleanup_frame(
    project_id: str,
    req: CleanupRequest,
    timestamp: float = 2.0
):
    """Generates a single-frame preview of the selected region edits."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if not req.authorization_confirmed:
        raise HTTPException(
            status_code=403,
            detail="Authorization confirmation required to preview video cleanup.",
        )
    if not math.isfinite(timestamp) or timestamp < 0 or timestamp > proj.metadata.duration:
        raise HTTPException(status_code=422, detail="Preview timestamp is outside the source video.")

    video_path = Path(proj.video_path)
    preview_url = render_cleanup_preview_frame(
        video_path=video_path,
        regions=req.regions,
        timestamp=timestamp,
        project_id=proj.id,
        metadata=proj.metadata
    )

    if not preview_url:
        raise HTTPException(status_code=500, detail="Failed to render preview frame")

    return {"preview_url": preview_url}

@app.post("/api/projects/{project_id}/cancel")
def cancel_job(project_id: str):
    """Request cancellation of an active processing job."""
    proj = project_store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.status not in {"analyzing", "generating", "cleaning", "exporting"}:
        raise HTTPException(status_code=409, detail="This project has no active processing job.")

    cancelled_jobs.add(project_id)
    proj.status_message = "Cancellation requested."
    project_store.save_project(proj)
    return {"success": True, "message": "Job cancellation signal sent"}
