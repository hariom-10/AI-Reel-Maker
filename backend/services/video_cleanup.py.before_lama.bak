import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import List, Optional, Callable

from config import FFMPEG_BIN, EXPORTS_DIR, THUMBNAILS_DIR
from models import CleanupRegion, VideoMetadata
from services.ffmpeg_runner import run_ffmpeg

logger = logging.getLogger(__name__)


def _drawtext_font_option() -> str:
    windows_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    candidates = [
        windows_fonts / "arial.ttf",
        windows_fonts / "segoeui.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    font_path = next((path for path in candidates if path.is_file()), None)
    if font_path is None:
        raise RuntimeError("No supported font was found for the text overlay.")
    escaped_path = font_path.resolve().as_posix().replace(":", r"\:")
    return f"fontfile='{escaped_path}'"


def build_cleanup_filters(regions: List[CleanupRegion], width: int, height: int) -> str:
    """Build a bounded FFmpeg filtergraph for user-selected region operations."""
    filters = []
    current_label = "[0:v]"

    for idx, reg in enumerate(regions):
        rx = min(width - 10, max(0, int(width * (reg.x / 100.0))))
        ry = min(height - 10, max(0, int(height * (reg.y / 100.0))))
        rw = max(10, min(width - rx, int(width * (reg.width / 100.0))))
        rh = max(10, min(height - ry, int(height * (reg.height / 100.0))))

        next_label = f"[v_step_{idx + 1}]"

        if reg.type == "inpaint":
            delogo = f"{current_label}delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0{next_label}"
            filters.append(delogo)
            current_label = next_label

        elif reg.type == "blur":
            # Gaussian / Box blur over rectangular region
            b_strength = max(5, reg.blur_strength)
            crop_blur = (
                f"{current_label}split[base_{idx}][to_blur_{idx}];"
                f"[to_blur_{idx}]crop={rw}:{rh}:{rx}:{ry},boxblur={b_strength}:4[blurred_{idx}];"
                f"[base_{idx}][blurred_{idx}]overlay={rx}:{ry}{next_label}"
            )
            filters.append(crop_blur)
            current_label = next_label

        elif reg.type == "add_text" and reg.replacement_text:
            clean_text = _escape_drawtext(reg.replacement_text)
            f_size = max(14, reg.font_size)
            txt_filter = (
                f"{current_label}drawtext={_drawtext_font_option()}:"
                f"text='{clean_text}':expansion=none:x={rx}:y={ry}:"
                f"fontsize={f_size}:fontcolor={reg.text_color}:"
                f"box=1:boxcolor={reg.bg_color}@{reg.bg_opacity}:boxborderw=6{next_label}"
            )
            filters.append(txt_filter)
            current_label = next_label

        elif reg.type == "replace_logo":
            delogo = f"{current_label}delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0"
            if reg.replacement_text:
                clean_text = _escape_drawtext(reg.replacement_text)
                txt = (
                    f"{delogo},drawtext={_drawtext_font_option()}:"
                    f"text='{clean_text}':expansion=none:x={rx}:y={ry}:"
                    f"fontsize={reg.font_size}:fontcolor={reg.text_color}:"
                    f"box=1:boxcolor=black@0.7:boxborderw=4{next_label}"
                )
                filters.append(txt)
            else:
                filters.append(f"{delogo}{next_label}")
            current_label = next_label

        else:
            filters.append(f"{current_label}null{next_label}")
            current_label = next_label

    filters.append(f"{current_label}null[cleanup_out]")
    return ";".join(filters)


def _escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )

def render_cleanup_video(
    video_path: Path,
    regions: List[CleanupRegion],
    project_id: str,
    metadata: VideoMetadata,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> Path:
    """
    Executes non-destructive FFmpeg region edits.
    The original video remains completely unchanged; a new high-quality derivative is produced.
    """
    output_filename = f"{project_id}_cleaned.mp4"
    output_path = EXPORTS_DIR / output_filename
    temp_output_path = EXPORTS_DIR / f"{project_id}_cleaned_{uuid.uuid4().hex}.tmp.mp4"

    width = metadata.width if metadata.width > 0 else 1920
    height = metadata.height if metadata.height > 0 else 1080

    filtergraph = build_cleanup_filters(regions, width, height)

    cmd = [
        FFMPEG_BIN,
        "-y",
        "-i", str(video_path),
        "-filter_complex", filtergraph,
        "-map", "[cleanup_out]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "19",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(temp_output_path)
    ]

    try:
        if progress_callback:
            progress_callback(15, "Applying authorized FFmpeg region edits...")

        run_ffmpeg(cmd, metadata.duration, progress_callback)

        if not temp_output_path.exists() or temp_output_path.stat().st_size <= 1000:
            raise RuntimeError("FFmpeg did not create a valid edited video.")
        if progress_callback:
            progress_callback(100, "Edited video rendered successfully.")
        temp_output_path.replace(output_path)
        return output_path
    except Exception:
        temp_output_path.unlink(missing_ok=True)
        raise

def render_cleanup_preview_frame(
    video_path: Path,
    regions: List[CleanupRegion],
    timestamp: float,
    project_id: str,
    metadata: VideoMetadata
) -> Optional[str]:
    """Render a single frame preview of the cleaned result for immediate Before/After inspection."""
    preview_filename = f"{project_id}_cleanup_preview.jpg"
    output_path = THUMBNAILS_DIR / preview_filename

    width = metadata.width if metadata.width > 0 else 1920
    height = metadata.height if metadata.height > 0 else 1080

    filtergraph = build_cleanup_filters(regions, width, height)

    cmd = [
        FFMPEG_BIN,
        "-y",
        "-ss", str(max(0.1, timestamp)),
        "-i", str(video_path),
        "-filter_complex", filtergraph,
        "-map", "[cleanup_out]",
        "-vframes", "1",
        "-q:v", "3",
        str(output_path)
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if output_path.exists():
            return f"/media/thumbnails/{preview_filename}"
        raise RuntimeError("FFmpeg did not create a cleanup preview frame.")
    except Exception:
        logger.exception("Cleanup preview frame failed.")
        raise
