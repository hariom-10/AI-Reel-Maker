import os
import subprocess
import logging
import zipfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from config import FFMPEG_BIN, EXPORTS_DIR, TEMP_DIR
from models import ClipConfig, Project, CropConfig, CaptionConfig, BlurRegion
from services.transcriber import generate_ass_subtitle_file

logger = logging.getLogger(__name__)

RESOLUTION_MAP = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080)
}

def escape_ffmpeg_path(path: Path) -> str:
    """Format file path safely for FFmpeg filter arguments on Windows."""
    p_str = path.resolve().as_posix()
    # In FFmpeg filter expressions, colons must be escaped like C\:/path
    p_str = p_str.replace(":", r"\:")
    return p_str

def build_filter_graph(
    crop_config: CropConfig,
    target_w: int,
    target_h: int,
    ass_subtitle_path: Optional[Path] = None
) -> str:
    """
    Construct FFmpeg filtergraph for vertical transformation,
    blur background, user privacy region blur, and subtitle overlay.
    """
    mode = crop_config.mode
    center_x = max(0.0, min(100.0, crop_config.center_x_percent)) / 100.0
    filters = []

    if mode == "blur_bg":
        # Background: scale to cover and blur heavily
        bg_filter = f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},boxblur=25:5,eq=brightness=-0.1[bg]"
        # Foreground: scale to fit inside target box
        fg_filter = f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fg]"
        overlay = f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
        filters.extend([bg_filter, fg_filter, overlay])
        current_pad = "[base]"
    elif mode == "fit":
        # Letterbox fit
        fit_filter = f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black[base]"
        filters.append(fit_filter)
        current_pad = "[base]"
    else:
        # Default: smart_crop (scale height/width to match and crop)
        # Scale so both dimensions cover target
        scale_filter = f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase"
        crop_x = f"(in_w-{target_w})*{center_x}"
        crop_filter = f"{scale_filter},crop={target_w}:{target_h}:{crop_x}:(in_h-{target_h})/2[base]"
        filters.append(crop_filter)
        current_pad = "[base]"

    # Optional user-selected blur region for personal footage/privacy
    if crop_config.blur_region and crop_config.blur_region.width > 0 and crop_config.blur_region.height > 0:
        reg = crop_config.blur_region
        rx = int(target_w * (reg.x / 100.0))
        ry = int(target_h * (reg.y / 100.0))
        rw = max(10, int(target_w * (reg.width / 100.0)))
        rh = max(10, int(target_h * (reg.height / 100.0)))
        # Delogo / boxblur over that patch
        blur_patch = f"{current_pad}delogo=x={rx}:y={ry}:w={rw}:h={rh}[blurred]"
        filters.append(blur_patch)
        current_pad = "[blurred]"

    # Burn subtitles if provided
    if ass_subtitle_path and ass_subtitle_path.exists():
        escaped_sub = escape_ffmpeg_path(ass_subtitle_path)
        sub_filter = f"{current_pad}ass='{escaped_sub}'[outv]"
        filters.append(sub_filter)
        return ";".join(filters), "[outv]"
    else:
        return ";".join(filters), current_pad

def render_clip(
    video_path: Path,
    clip: ClipConfig,
    project_id: str,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> ClipConfig:
    """Render a single vertical reel clip with trim, formatting, and captions."""
    target_w, target_h = RESOLUTION_MAP.get(clip.crop_config.aspect_ratio, (1080, 1920))
    output_filename = f"{project_id}_{clip.clip_id}.mp4"
    output_path = EXPORTS_DIR / output_filename

    # Subtitle ASS generation
    ass_path = None
    if clip.caption_config.enabled and clip.subtitles:
        ass_filename = f"{project_id}_{clip.clip_id}.ass"
        ass_path = TEMP_DIR / ass_filename
        generate_ass_subtitle_file(
            subtitles=clip.subtitles,
            config=clip.caption_config,
            clip_start_time=clip.start_time,
            output_path=ass_path,
            target_width=target_w,
            target_height=target_h
        )

    # Build filtergraph
    filter_complex, out_label = build_filter_graph(
        crop_config=clip.crop_config,
        target_w=target_w,
        target_h=target_h,
        ass_subtitle_path=ass_path
    )

    clip_duration = round(clip.end_time - clip.start_time, 2)
    if clip_duration <= 0:
        clip_duration = 15.0

    cmd = [
        FFMPEG_BIN,
        "-y",
        "-ss", str(clip.start_time),
        "-t", str(clip_duration),
        "-i", str(video_path),
        "-filter_complex", filter_complex,
        "-map", out_label,
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-r", "30",
        "-movflags", "+faststart",
        str(output_path)
    ]

    try:
        if progress_callback:
            progress_callback(20, f"Rendering {clip.title}...")

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        
        if output_path.exists() and output_path.stat().st_size > 1000:
            clip.status = "exported"
            clip.output_path = str(output_path)
            clip.output_url = f"/media/exports/{output_filename}"
            if progress_callback:
                progress_callback(100, f"Completed {clip.title}")
        else:
            clip.status = "error"
            clip.error_message = "Output file is empty or corrupted."
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg render error for {clip.clip_id}: {e.stderr}")
        clip.status = "error"
        clip.error_message = f"Render failed: {e.stderr[-300:] if e.stderr else 'unknown error'}"
    except Exception as e:
        logger.error(f"Render exception: {e}")
        clip.status = "error"
        clip.error_message = str(e)
    finally:
        # Clean up temporary ASS file
        if ass_path and ass_path.exists():
            try:
                ass_path.unlink()
            except Exception:
                pass

    return clip

def create_export_zip(project_id: str, clips: List[ClipConfig]) -> Optional[str]:
    """Create a downloadable ZIP archive containing all finished exported clips."""
    zip_filename = f"{project_id}_reels_bundle.zip"
    zip_path = EXPORTS_DIR / zip_filename

    exported_files = []
    for clip in clips:
        if clip.status == "exported" and clip.output_path:
            p = Path(clip.output_path)
            if p.exists():
                exported_files.append((p, f"{clip.clip_id}_{clip.title.replace(' ', '_')}.mp4"))

    if not exported_files:
        return None

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path, arcname in exported_files:
            zipf.write(file_path, arcname=arcname)

    return f"/media/exports/{zip_filename}"
