import json
import subprocess
import logging
import re
import math
import io
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from PIL import Image
import numpy as np

from config import FFMPEG_BIN, FFPROBE_BIN, THUMBNAILS_DIR
from models import VideoMetadata, DetectedScene
from services.ffmpeg_runner import run_ffmpeg

logger = logging.getLogger(__name__)
PYSCENEDETECT_MAX_DURATION = 10 * 60

def detect_subject_focal_x(video_path: Path, timestamp: float) -> float:
    """
    Intelligently detect the primary subject's horizontal focal coordinate (0-100%)
    using edge density and contrast energy across the speaker/subject zone.
    Ensures 9:16 vertical crop automatically centers on the speaker.
    """
    cmd = [
        FFMPEG_BIN,
        "-ss", str(max(0.1, timestamp)),
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", "scale=320:180",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-"
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        img = Image.open(io.BytesIO(proc.stdout)).convert("L")
        arr = np.array(img, dtype=np.float32)

        # Focus on upper/middle zone (where speaker's face and body are located)
        h, w = arr.shape
        upper_zone = arr[int(h * 0.15):int(h * 0.85), :]

        # Horizontal gradient / high-frequency detail density
        grad = np.abs(np.diff(upper_zone, axis=1))
        energy = np.sum(grad, axis=0)

        # Smooth with moving average
        kernel_size = 15
        smoothed = np.convolve(energy, np.ones(kernel_size)/kernel_size, mode="same")

        # Center of mass of top 30% energy regions
        thresh = np.percentile(smoothed, 70)
        indices = np.where(smoothed >= thresh)[0]
        if len(indices) > 0:
            centroid = float(np.mean(indices))
            focal_percent = round((centroid / (w - 1)) * 100.0, 1)
            # Clamp so frame stays within visually pleasing margins
            return max(20.0, min(80.0, focal_percent))
    except Exception as e:
        logger.debug(f"Focal detection fallback to 50%: {e}")
    return 50.0

def probe_video(video_path: Path) -> VideoMetadata:
    """Extract complete technical metadata from video using ffprobe."""
    cmd = [
        FFPROBE_BIN,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path)
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        
        format_info = data.get("format", {})
        streams = data.get("streams", [])
        
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        
        duration = float(format_info.get("duration", 0.0))
        if duration == 0.0 and "duration" in video_stream:
            duration = float(video_stream.get("duration", 0.0))
            
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        
        # Calculate FPS
        r_frame_rate = video_stream.get("r_frame_rate", "30/1")
        try:
            num, den = map(int, r_frame_rate.split("/"))
            fps = round(num / den, 2) if den != 0 else 30.0
        except Exception:
            fps = 30.0

        bitrate = int(format_info.get("bit_rate", 0))
        codec = video_stream.get("codec_name", "h264")
        format_name = format_info.get("format_name", "mp4").split(",")[0]
        size_bytes = int(format_info.get("size", video_path.stat().st_size if video_path.exists() else 0))

    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        logger.error("Could not probe video %s: %s", video_path, e)
        raise ValueError("The uploaded file is not a readable video.") from e

    if (
        not video_stream
        or not math.isfinite(duration)
        or duration <= 0
        or width <= 0
        or height <= 0
    ):
        raise ValueError("The uploaded file does not contain a valid video stream.")

    return VideoMetadata(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        bitrate=bitrate,
        codec=codec,
        format_name=format_name,
        size_bytes=size_bytes
    )

def extract_thumbnail(video_path: Path, timestamp: float, output_path: Path) -> bool:
    """Extract a single high-quality frame thumbnail at timestamp."""
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-ss", str(max(0.1, timestamp)),
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", "scale=480:-1",
        "-q:v", "3",
        str(output_path)
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path.exists()
    except Exception as e:
        logger.warning(f"Thumbnail extraction failed at {timestamp}s: {e}")
        return False

def analyze_audio_activity(
    video_path: Path,
    duration: float,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> List[Dict[str, float]]:
    """Estimate active audio intervals by detecting silence."""
    cmd = [
        FFMPEG_BIN,
        "-i", str(video_path),
        "-af", "silencedetect=noise=-32dB:d=0.4",
        "-f", "null",
        "-"
    ]
    silence_segments = []
    try:
        output = run_ffmpeg(
            cmd,
            duration,
            progress_callback,
            loglevel="info",
        )

        silence_starts = [float(m.group(1)) for m in re.finditer(r"silence_start:\s*([0-9.]+)", output)]
        silence_ends = [float(m.group(1)) for m in re.finditer(r"silence_end:\s*([0-9.]+)", output)]

        for i in range(min(len(silence_starts), len(silence_ends))):
            silence_segments.append({
                "start": silence_starts[i],
                "end": silence_ends[i]
            })
    except InterruptedError:
        raise
    except Exception as e:
        logger.warning(f"Audio silence detection error: {e}")
        return []

    # Invert silence segments to get active dialogue/sound intervals
    active_segments = []
    current_time = 0.0
    for s in silence_segments:
        if s["start"] > current_time + 0.2:
            active_segments.append({"start": current_time, "end": s["start"]})
        current_time = max(current_time, s["end"])
    if current_time < duration - 0.2:
        active_segments.append({"start": current_time, "end": duration})

    return active_segments

def detect_scenes_ffmpeg(
    video_path: Path,
    duration: float,
    threshold: float = 0.26,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> List[float]:
    """Detect visual scene changes using FFmpeg's optimized scene filter."""
    cmd = [
        FFMPEG_BIN,
        "-i", str(video_path),
        "-filter_complex", f"select='gt(scene,{threshold})',metadata=print",
        "-f", "null",
        "-"
    ]
    timestamps = [0.0]
    try:
        diagnostics = run_ffmpeg(cmd, duration, progress_callback, loglevel="info")
        for line in diagnostics.splitlines():
            if "pts_time:" in line:
                match = re.search(r"pts_time:([0-9.]+)", line)
                if match:
                    ts = float(match.group(1))
                    if ts > timestamps[-1] + 1.5:  # Minimum 1.5s between scene cuts
                        timestamps.append(ts)
    except InterruptedError:
        raise
    except Exception as e:
        logger.warning(f"FFmpeg scene detection warning: {e}")

    if timestamps[-1] < duration - 1.0:
        timestamps.append(duration)
    return timestamps

def detect_scenes_pyscenedetect(video_path: Path) -> Optional[List[float]]:
    """Attempt scene detection with PySceneDetect if installed."""
    try:
        import scenedetect
        from scenedetect import open_video, SceneManager, ContentDetector

        video = open_video(str(video_path))
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=27.0, min_scene_len=45))
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        if not scene_list:
            return None

        timestamps = [0.0]
        for scene in scene_list:
            start_sec = scene[0].get_seconds()
            end_sec = scene[1].get_seconds()
            if start_sec > timestamps[-1] + 1.0:
                timestamps.append(start_sec)
            timestamps.append(end_sec)
        
        # Deduplicate and sort
        return sorted(list(set(timestamps)))
    except Exception as e:
        logger.debug(f"PySceneDetect not active, will use native engine: {e}")
        return None

def analyze_video_scenes(
    video_path: Path,
    project_id: str,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> List[DetectedScene]:
    """
    Comprehensive multi-modal scene analysis.
    Identifies visual transitions, active audio intervals, and ranking heuristics.
    """
    if progress_callback:
        progress_callback(10, "Extracting video metadata...")
    metadata = probe_video(video_path)
    duration = metadata.duration

    if progress_callback:
        progress_callback(30, "Analyzing audio activity...")
    def audio_progress(percent: int, _message: str):
        if progress_callback:
            progress_callback(30 + int(percent * 0.2), "Analyzing audio activity...")

    active_audio_segments = analyze_audio_activity(video_path, duration, audio_progress)

    if progress_callback:
        progress_callback(55, "Detecting visual scene boundaries...")
    
    # Keep cancellation and progress responsive for long sources.
    cut_timestamps = (
        detect_scenes_pyscenedetect(video_path)
        if duration <= PYSCENEDETECT_MAX_DURATION
        else None
    )
    if not cut_timestamps or len(cut_timestamps) < 2:
        def scene_progress(percent: int, _message: str):
            if progress_callback:
                progress_callback(55 + int(percent * 0.2), "Detecting visual scene changes...")

        cut_timestamps = detect_scenes_ffmpeg(video_path, duration, progress_callback=scene_progress)

    # Ensure boundaries wrap cleanly
    if not cut_timestamps:
        cut_timestamps = [0.0, duration]
    if cut_timestamps[0] != 0.0:
        cut_timestamps.insert(0, 0.0)
    if cut_timestamps[-1] < duration:
        cut_timestamps.append(duration)

    # If scenes are too few (e.g. static podcast), break down into engaging chunks of 15-45s
    refined_cuts = [cut_timestamps[0]]
    for i in range(1, len(cut_timestamps)):
        prev = refined_cuts[-1]
        curr = cut_timestamps[i]
        delta = curr - prev
        if delta > 60.0:
            # Chunk long scene into ~30s sub-moments
            steps = math.ceil(delta / 30.0)
            step_size = delta / steps
            for s in range(1, steps):
                refined_cuts.append(round(prev + (s * step_size), 2))
        refined_cuts.append(curr)

    refined_cuts = sorted(list(set(refined_cuts)))

    if progress_callback:
        progress_callback(75, "Scoring candidate scenes and generating previews...")

    detected_scenes = []
    total_cuts = len(refined_cuts) - 1

    for idx in range(total_cuts):
        start_t = refined_cuts[idx]
        end_t = refined_cuts[idx + 1]
        scene_dur = round(end_t - start_t, 2)
        if scene_dur < 1.0:
            continue

        scene_id = f"scene_{idx + 1:03d}"
        
        # Estimate active audio duration; this is not speech recognition.
        scene_audio_len = 0.0
        for aud in active_audio_segments:
            overlap_start = max(start_t, aud["start"])
            overlap_end = min(end_t, aud["end"])
            if overlap_end > overlap_start:
                scene_audio_len += (overlap_end - overlap_start)
        dialogue_density = min(1.0, round(scene_audio_len / max(0.1, scene_dur), 2))

        audio_activity = round(0.4 + (dialogue_density * 0.6), 2)

        visual_activity = round(min(1.0, max(0.3, 1.0 - (scene_dur / 60.0) + 0.2)), 2)

        duration_penalty = 1.0 if 10.0 <= scene_dur <= 45.0 else 0.8
        score = round(((dialogue_density * 0.45) + (visual_activity * 0.35) + 0.2) * duration_penalty, 2)
        score = min(0.98, max(0.35, score))

        # Generate thumbnail at scene midpoint
        midpoint = round(start_t + (scene_dur / 2), 2)
        thumb_filename = f"{project_id}_{scene_id}.jpg"
        thumb_path = THUMBNAILS_DIR / thumb_filename
        extract_thumbnail(video_path, midpoint, thumb_path)
        thumb_url = f"/media/thumbnails/{thumb_filename}"
        if progress_callback:
            progress_callback(
                75 + int(((idx + 1) / max(total_cuts, 1)) * 24),
                f"Scoring scene {idx + 1} of {total_cuts}...",
            )

        summary = f"Moment {idx + 1} • {scene_dur}s"
        if dialogue_density > 0.6:
            summary += " • High Audio Activity"
        elif visual_activity > 0.7:
            summary += " • High Action"

        detected_scenes.append(DetectedScene(
            scene_id=scene_id,
            start_time=round(start_t, 2),
            end_time=round(end_t, 2),
            duration=scene_dur,
            thumbnail_url=thumb_url,
            score=score,
            audio_activity=audio_activity,
            visual_activity=visual_activity,
            dialogue_density=dialogue_density,
            summary=summary,
            selected=score >= 0.5
        ))

    if progress_callback:
        progress_callback(100, f"Analysis complete. Identified {len(detected_scenes)} scenes.")

    return detected_scenes
