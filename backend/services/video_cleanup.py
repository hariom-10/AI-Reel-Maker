import json
import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional, Callable

from config import FFMPEG_BIN, EXPORTS_DIR, THUMBNAILS_DIR
from models import CleanupRegion, VideoMetadata
from services.ffmpeg_runner import run_ffmpeg

logger = logging.getLogger(__name__)

LAMA_PYTHON = Path(r"C:\AI-Models\LaMa\venv\Scripts\python.exe")
LAMA_SCRIPT = Path(r"C:\AI-Models\LaMa\lama_video_frames.py")
LAMA_MODEL = Path(r"C:\AI-Models\LaMa\models\big-lama.pt")


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
    """Build FFmpeg filters for non-inpaint operations."""
    filters = []
    current_label = "[0:v]"
    step = 0

    for reg in regions:
        if reg.type == "inpaint":
            continue

        idx = step
        step += 1

        rx = min(width - 10, max(0, int(width * (reg.x / 100.0))))
        ry = min(height - 10, max(0, int(height * (reg.y / 100.0))))
        rw = max(10, min(width - rx, int(width * (reg.width / 100.0))))
        rh = max(10, min(height - ry, int(height * (reg.height / 100.0))))

        next_label = f"[v_step_{idx + 1}]"

        if reg.type == "blur":
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


def _inpaint_regions(regions: List[CleanupRegion]) -> List[CleanupRegion]:
    return [region for region in regions if region.type == "inpaint"]


def _non_inpaint_regions(regions: List[CleanupRegion]) -> List[CleanupRegion]:
    return [region for region in regions if region.type != "inpaint"]


def _run_lama_frames(
    input_dir: Path,
    output_dir: Path,
    regions: List[CleanupRegion],
    progress_callback: Optional[Callable[[int, str], None]] = None,
    progress_start: int = 20,
    progress_end: int = 85,
) -> None:
    """Run the isolated Python 3.8 LaMa CPU environment on extracted frames."""
    if not LAMA_PYTHON.is_file():
        raise RuntimeError(f"LaMa Python environment not found: {LAMA_PYTHON}")
    if not LAMA_SCRIPT.is_file():
        raise RuntimeError(f"LaMa helper script not found: {LAMA_SCRIPT}")
    if not LAMA_MODEL.is_file():
        raise RuntimeError(f"LaMa model not found: {LAMA_MODEL}")

    output_dir.mkdir(parents=True, exist_ok=True)
    region_data = [
        {
            "x": region.x,
            "y": region.y,
            "width": region.width,
            "height": region.height,
        }
        for region in regions
    ]

    regions_file = input_dir.parent / f"lama_regions_{uuid.uuid4().hex}.json"
    with regions_file.open("w", encoding="utf-8") as file:
        json.dump(region_data, file)

    env = os.environ.copy()
    env["LAMA_MODEL"] = str(LAMA_MODEL)

    command = [
        str(LAMA_PYTHON),
        str(LAMA_SCRIPT),
        "--input", str(input_dir),
        "--output", str(output_dir),
        "--regions", str(regions_file),
    ]

    process = None
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )

        total = 0
        last_progress = -1

        if process.stdout is None:
            raise RuntimeError("LaMa progress stream was not created.")

        for line in process.stdout:
            line = line.strip()
            if line.startswith("PROGRESS "):
                parts = line.split()
                if len(parts) == 3:
                    current, total = int(parts[1]), int(parts[2])
                    pct = progress_start + int(
                        (current / max(total, 1)) * (progress_end - progress_start)
                    )
                    if progress_callback and pct != last_progress:
                        progress_callback(pct, f"AI inpainting frame {current}/{total}...")
                        last_progress = pct
            elif line.startswith("LAMA_ERROR:"):
                logger.error(line)
            elif line:
                logger.info("LaMa: %s", line)

        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"LaMa frame processing failed (exit code {return_code}).")

        expected = list(input_dir.glob("frame_*.png"))
        produced = list(output_dir.glob("frame_*.png"))
        if not expected or len(produced) != len(expected):
            raise RuntimeError(
                f"LaMa output frame count mismatch: expected {len(expected)}, got {len(produced)}."
            )

    except BaseException:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise
    finally:
        regions_file.unlink(missing_ok=True)


def _render_lama_video(
    video_path: Path,
    output_path: Path,
    temp_output_path: Path,
    regions: List[CleanupRegion],
    metadata: VideoMetadata,
    progress_callback: Optional[Callable[[int, str], None]],
) -> Path:
    """Extract frames, inpaint sequentially with LaMa, then encode with original audio."""
    inpaint = _inpaint_regions(regions)
    other_regions = _non_inpaint_regions(regions)

    with tempfile.TemporaryDirectory(
        prefix="lama_cleanup_",
        dir=str(EXPORTS_DIR),
    ) as temp_name:
        work_dir = Path(temp_name)
        input_dir = work_dir / "input_frames"
        output_dir = work_dir / "lama_frames"
        input_dir.mkdir()
        output_dir.mkdir()

        frame_pattern = str(input_dir / "frame_%08d.png")
        extract_cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(video_path),
            "-map", "0:v:0",
            "-vsync", "0",
            "-start_number", "1",
            frame_pattern,
        ]

        if progress_callback:
            progress_callback(10, "Extracting video frames for AI inpainting...")

        run_ffmpeg(
            extract_cmd,
            metadata.duration,
            lambda pct, msg: progress_callback(
                10 + int(pct * 0.10), "Extracting video frames..."
            ) if progress_callback else None,
        )

        _run_lama_frames(
            input_dir,
            output_dir,
            inpaint,
            progress_callback,
            20,
            85,
        )

        fps = metadata.fps if metadata.fps > 0 else 30.0
        filtergraph = build_cleanup_filters(
            other_regions,
            metadata.width if metadata.width > 0 else 1920,
            metadata.height if metadata.height > 0 else 1080,
        )

        encode_cmd = [
            FFMPEG_BIN, "-y",
            "-framerate", str(fps),
            "-i", str(output_dir / "frame_%08d.png"),
            "-i", str(video_path),
            "-filter_complex", filtergraph,
            "-map", "[cleanup_out]",
            "-map", "1:a?",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "19",
            "-c:a", "aac",
            "-shortest",
            "-movflags", "+faststart",
            str(temp_output_path),
        ]

        if progress_callback:
            progress_callback(86, "Encoding cleaned video and restoring original audio...")

        run_ffmpeg(
            encode_cmd,
            metadata.duration,
            lambda pct, msg: progress_callback(
                86 + int(pct * 0.13), "Encoding AI-cleaned video..."
            ) if progress_callback else None,
        )

    if not temp_output_path.exists() or temp_output_path.stat().st_size <= 1000:
        raise RuntimeError("FFmpeg did not create a valid AI-cleaned video.")

    temp_output_path.replace(output_path)
    return output_path


def render_cleanup_video(
    video_path: Path,
    regions: List[CleanupRegion],
    project_id: str,
    metadata: VideoMetadata,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> Path:
    """Render a separate cleaned video; never modifies the original source."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    output_path = EXPORTS_DIR / f"{project_id}_cleaned.mp4"
    temp_output_path = EXPORTS_DIR / f"{project_id}_cleaned_{uuid.uuid4().hex}.tmp.mp4"

    try:
        if _inpaint_regions(regions):
            if progress_callback:
                progress_callback(5, "Starting LaMa AI video cleanup...")
            return _render_lama_video(
                video_path,
                output_path,
                temp_output_path,
                regions,
                metadata,
                progress_callback,
            )

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
            str(temp_output_path),
        ]

        if progress_callback:
            progress_callback(15, "Applying authorized FFmpeg region edits...")

        run_ffmpeg(cmd, metadata.duration, progress_callback)

        if not temp_output_path.exists() or temp_output_path.stat().st_size <= 1000:
            raise RuntimeError("FFmpeg did not create a valid edited video.")

        temp_output_path.replace(output_path)
        if progress_callback:
            progress_callback(100, "Edited video rendered successfully.")
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
    """Render a single-frame preview using the same LaMa inpainting path."""
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    preview_filename = f"{project_id}_cleanup_preview.jpg"
    output_path = THUMBNAILS_DIR / preview_filename

    width = metadata.width if metadata.width > 0 else 1920
    height = metadata.height if metadata.height > 0 else 1080
    inpaint = _inpaint_regions(regions)
    other_regions = _non_inpaint_regions(regions)

    try:
        if inpaint:
            with tempfile.TemporaryDirectory(
                prefix="lama_preview_",
                dir=str(THUMBNAILS_DIR),
            ) as temp_name:
                work_dir = Path(temp_name)
                input_dir = work_dir / "input"
                output_dir = work_dir / "output"
                input_dir.mkdir()
                output_dir.mkdir()

                input_frame = input_dir / "frame_00000001.png"
                extract_cmd = [
                    FFMPEG_BIN, "-y",
                    "-ss", str(max(0.0, timestamp)),
                    "-i", str(video_path),
                    "-frames:v", "1",
                    str(input_frame),
                ]
                subprocess.run(
                    extract_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )

                if not input_frame.exists():
                    raise RuntimeError("FFmpeg did not extract the preview frame.")

                _run_lama_frames(input_dir, output_dir, inpaint)

                filtergraph = build_cleanup_filters(other_regions, width, height)
                preview_cmd = [
                    FFMPEG_BIN, "-y",
                    "-i", str(output_dir / input_frame.name),
                    "-filter_complex", filtergraph,
                    "-map", "[cleanup_out]",
                    "-frames:v", "1",
                    "-q:v", "3",
                    str(output_path),
                ]
                subprocess.run(
                    preview_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
        else:
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
                str(output_path),
            ]
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

        if output_path.exists():
            return f"/media/thumbnails/{preview_filename}"
        raise RuntimeError("FFmpeg did not create a cleanup preview frame.")

    except Exception:
        output_path.unlink(missing_ok=True)
        logger.exception("Cleanup preview frame failed.")
        raise
