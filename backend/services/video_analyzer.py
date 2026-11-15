import io
import json
import logging
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from config import FFMPEG_BIN, FFPROBE_BIN, THUMBNAILS_DIR
from models import DetectedScene, SubtitleItem, VideoMetadata
from services.ffmpeg_runner import run_ffmpeg
from services.transcriber import transcribe_video, whisper_available

logger = logging.getLogger(__name__)

VISUAL_SAMPLE_INTERVAL = 2.0
VISUAL_SAMPLE_WIDTH = 160
VISUAL_SAMPLE_HEIGHT = 90
HIGHLIGHT_SCORING_WEIGHTS = {
    "speech": 0.30,
    "audio": 0.18,
    "visual": 0.20,
    "scene_duration": 0.10,
    "scene_boundary": 0.08,
    "dialogue_context": 0.14,
}


def detect_subject_focal_x(video_path: Path, timestamp: float) -> float:
    """Estimate a crop focal point from edge density in one sampled frame."""
    cmd = [
        FFMPEG_BIN,
        "-ss", str(max(0.1, timestamp)),
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", "scale=320:180",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-",
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        img = Image.open(io.BytesIO(proc.stdout)).convert("L")
        arr = np.array(img, dtype=np.float32)
        height, width = arr.shape
        upper_zone = arr[int(height * 0.15):int(height * 0.85), :]
        gradient = np.abs(np.diff(upper_zone, axis=1))
        energy = np.sum(gradient, axis=0)
        smoothed = np.convolve(energy, np.ones(15) / 15, mode="same")
        indices = np.where(smoothed >= np.percentile(smoothed, 70))[0]
        if len(indices) > 0:
            focal_percent = round((float(np.mean(indices)) / (width - 1)) * 100.0, 1)
            return max(20.0, min(80.0, focal_percent))
    except Exception as exc:
        logger.debug("Focal detection fallback to 50%%: %s", exc)
    return 50.0


def probe_video(video_path: Path) -> VideoMetadata:
    """Extract technical metadata from a video using FFprobe."""
    cmd = [
        FFPROBE_BIN,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        format_info = data.get("format", {})
        streams = data.get("streams", [])
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
        duration = float(format_info.get("duration", 0.0))
        if duration == 0.0 and "duration" in video_stream:
            duration = float(video_stream.get("duration", 0.0))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))

        try:
            numerator, denominator = map(int, video_stream.get("r_frame_rate", "30/1").split("/"))
            fps = round(numerator / denominator, 2) if denominator else 30.0
        except (ValueError, ZeroDivisionError):
            fps = 30.0

        bitrate = int(format_info.get("bit_rate", 0))
        codec = video_stream.get("codec_name", "h264")
        format_name = format_info.get("format_name", "mp4").split(",")[0]
        size_bytes = int(format_info.get("size", video_path.stat().st_size if video_path.exists() else 0))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        logger.error("Could not probe video %s: %s", video_path, exc)
        raise ValueError("The uploaded file is not a readable video.") from exc

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
        size_bytes=size_bytes,
    )


def extract_thumbnail(video_path: Path, timestamp: float, output_path: Path) -> bool:
    """Extract a high-quality frame thumbnail at a timestamp."""
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-ss", str(max(0.1, timestamp)),
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", "scale=480:-1",
        "-q:v", "3",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_path.exists()
    except Exception as exc:
        logger.warning("Thumbnail extraction failed at %ss: %s", timestamp, exc)
        return False


def analyze_audio_activity(
    video_path: Path,
    duration: float,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> List[Dict[str, float]]:
    """Estimate audio-active intervals as the complement of FFmpeg silence intervals."""
    cmd = [
        FFMPEG_BIN,
        "-i", str(video_path),
        "-af", "silencedetect=noise=-32dB:d=0.4",
        "-vn",
        "-f", "null",
        "-",
    ]
    try:
        output = run_ffmpeg(cmd, duration, progress_callback, loglevel="info")
    except InterruptedError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        logger.info("Audio activity unavailable for %s: %s", video_path, exc)
        return []

    events = [
        (float(match.group(2)), match.group(1))
        for match in re.finditer(r"(silence_start|silence_end):\s*([0-9.]+)", output)
    ]
    active_segments: List[Dict[str, float]] = []
    current_time = 0.0
    in_silence = False
    for timestamp, event in events:
        timestamp = min(duration, max(0.0, timestamp))
        if event == "silence_start" and not in_silence:
            if timestamp > current_time + 0.2:
                active_segments.append({"start": current_time, "end": timestamp})
            in_silence = True
        elif event == "silence_end" and in_silence:
            current_time = timestamp
            in_silence = False

    if not in_silence and duration > current_time + 0.2:
        active_segments.append({"start": current_time, "end": duration})
    return active_segments


def detect_scenes_ffmpeg(
    video_path: Path,
    duration: float,
    threshold: float = 0.26,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> List[float]:
    """Detect cuts on a low-resolution, 2-fps stream to bound filter cost."""
    filter_graph = (
        "fps=2,scale=320:-2:flags=fast_bilinear,"
        f"select='gt(scene,{threshold})',metadata=print"
    )
    cmd = [
        FFMPEG_BIN,
        "-i", str(video_path),
        "-vf", filter_graph,
        "-an",
        "-sn",
        "-dn",
        "-f", "null",
        "-",
    ]
    timestamps = [0.0]
    try:
        diagnostics = run_ffmpeg(cmd, duration, progress_callback, loglevel="info")
        for match in re.finditer(r"pts_time:([0-9.]+)", diagnostics):
            timestamp = float(match.group(1))
            if timestamp > timestamps[-1] + 1.0:
                timestamps.append(timestamp)
    except InterruptedError:
        raise
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.warning("FFmpeg scene detection failed for %s: %s", video_path, exc)

    if timestamps[-1] < duration:
        timestamps.append(duration)
    return timestamps


def sample_visual_activity(
    video_path: Path,
    duration: float,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> List[Tuple[float, float]]:
    """Stream tiny grayscale samples and measure frame-to-frame pixel change."""
    cmd = [
        FFMPEG_BIN,
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(video_path),
        "-vf", (
            f"fps=1/{VISUAL_SAMPLE_INTERVAL},"
            f"scale={VISUAL_SAMPLE_WIDTH}:{VISUAL_SAMPLE_HEIGHT}:flags=fast_bilinear,"
            "format=gray"
        ),
        "-an",
        "-sn",
        "-dn",
        "-f", "rawvideo",
        "-pix_fmt", "gray",
        "pipe:1",
    ]
    frame_bytes = VISUAL_SAMPLE_WIDTH * VISUAL_SAMPLE_HEIGHT
    samples: List[Tuple[float, float]] = []
    previous: Optional[np.ndarray] = None

    try:
        with tempfile.TemporaryFile() as error_stream:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=error_stream,
            )
            try:
                if process.stdout is None:
                    raise RuntimeError("FFmpeg visual sample stream was not created.")
                frame_index = 0
                while True:
                    raw_frame = process.stdout.read(frame_bytes)
                    if not raw_frame:
                        break
                    if len(raw_frame) != frame_bytes:
                        raise ValueError("FFmpeg returned an incomplete visual sample.")
                    current = np.frombuffer(raw_frame, dtype=np.uint8)
                    change = (
                        float(np.abs(current.astype(np.int16) - previous.astype(np.int16)).mean())
                        if previous is not None
                        else 0.0
                    )
                    samples.append((
                        frame_index * VISUAL_SAMPLE_INTERVAL,
                        min(1.0, change / 40.0),
                    ))
                    previous = current
                    frame_index += 1
                    if progress_callback and frame_index % 10 == 0:
                        percent = min(99, int(frame_index * VISUAL_SAMPLE_INTERVAL / max(duration, 0.1) * 100))
                        progress_callback(percent, "Sampling visual changes...")

                return_code = process.wait()
                error_stream.seek(0)
                diagnostics = error_stream.read().decode("utf-8", errors="replace")
                if return_code:
                    raise subprocess.CalledProcessError(
                        return_code,
                        cmd,
                        output=diagnostics[-4000:],
                    )
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                raise
    except InterruptedError:
        raise
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.warning("Visual change sampling unavailable for %s: %s", video_path, exc)
        return []

    return samples


def _overlap_duration(start: float, end: float, intervals: List[Tuple[float, float]]) -> float:
    return sum(max(0.0, min(end, interval_end) - max(start, interval_start))
               for interval_start, interval_end in intervals)


def _weighted_score(values: Dict[str, float]) -> float:
    available_weight = sum(HIGHLIGHT_SCORING_WEIGHTS[key] for key in values)
    if not available_weight:
        return 0.0
    return sum(HIGHLIGHT_SCORING_WEIGHTS[key] * value for key, value in values.items()) / available_weight


def analyze_video_scenes(
    video_path: Path,
    project_id: str,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> List[DetectedScene]:
    """Analyze scene cuts, audio activity, optional Whisper speech, and sampled visual change."""
    if progress_callback:
        progress_callback(2, "Extracting video metadata...")
    metadata = probe_video(video_path)
    duration = metadata.duration

    def audio_progress(percent: int, _message: str):
        if progress_callback:
            progress_callback(5 + int(percent * 0.15), "Analyzing audio activity...")

    active_audio_segments = analyze_audio_activity(video_path, duration, audio_progress)

    def scene_progress(percent: int, _message: str):
        if progress_callback:
            progress_callback(22 + int(percent * 0.22), "Detecting low-resolution scene changes...")

    cut_timestamps = detect_scenes_ffmpeg(
        video_path,
        duration,
        progress_callback=scene_progress,
    )

    transcript: Optional[List[SubtitleItem]] = None

    def transcription_progress(percent: int, message: str):
        if progress_callback:
            progress_callback(45 + int(percent * 0.32), message)

    try:
        transcript = transcribe_video(
            video_path,
            project_id,
            duration,
            progress_callback=transcription_progress,
        )
    except InterruptedError:
        raise
    except Exception as exc:
        logger.warning("Whisper analysis unavailable for %s: %s", video_path, exc)
    if transcript is None and progress_callback and not whisper_available():
        progress_callback(
            77,
            "Whisper Base package or local weights unavailable; speech scoring is skipped.",
        )

    def visual_progress(percent: int, _message: str):
        if progress_callback:
            progress_callback(78 + int(percent * 0.11), "Sampling visual changes...")

    visual_samples = sample_visual_activity(video_path, duration, visual_progress)

    if not cut_timestamps:
        cut_timestamps = [0.0, duration]
    cut_timestamps = sorted({
        round(min(duration, max(0.0, timestamp)), 2)
        for timestamp in cut_timestamps
    })
    if not cut_timestamps or cut_timestamps[0] != 0.0:
        cut_timestamps.insert(0, 0.0)
    if cut_timestamps[-1] < duration:
        cut_timestamps.append(duration)

    refined_cuts = [cut_timestamps[0]]
    for timestamp in cut_timestamps[1:]:
        previous = refined_cuts[-1]
        segment_duration = timestamp - previous
        if segment_duration > 60.0:
            steps = math.ceil(segment_duration / 30.0)
            step_size = segment_duration / steps
            for step in range(1, steps):
                refined_cuts.append(round(previous + step * step_size, 2))
        refined_cuts.append(timestamp)
    refined_cuts = sorted(set(refined_cuts))

    audio_intervals = [(segment["start"], segment["end"]) for segment in active_audio_segments]
    speech_intervals = (
        [(item.start_time, item.end_time) for item in transcript or []]
        if transcript is not None
        else None
    )
    detected_scenes: List[DetectedScene] = []
    total_scenes = len(refined_cuts) - 1
    for index in range(total_scenes):
        start_time = refined_cuts[index]
        end_time = refined_cuts[index + 1]
        scene_duration = round(end_time - start_time, 2)
        if scene_duration < 1.0:
            continue

        scene_audio_duration = _overlap_duration(start_time, end_time, audio_intervals)
        audio_activity = min(1.0, scene_audio_duration / max(scene_duration, 0.1))
        scene_speech_duration = (
            _overlap_duration(start_time, end_time, speech_intervals)
            if speech_intervals is not None
            else 0.0
        )
        dialogue_density = min(1.0, scene_speech_duration / max(scene_duration, 0.1))

        scene_visual_values = [
            value for timestamp, value in visual_samples
            if start_time <= timestamp < end_time
        ]
        visual_activity = (
            sum(scene_visual_values) / len(scene_visual_values)
            if scene_visual_values
            else 0.0
        )
        duration_score = max(0.0, 1.0 - abs(scene_duration - 30.0) / 60.0)
        start_is_cut = any(abs(start_time - cut) <= 0.75 for cut in cut_timestamps)
        end_is_cut = any(abs(end_time - cut) <= 0.75 for cut in cut_timestamps)
        boundary_score = (float(start_is_cut) + float(end_is_cut)) / 2.0

        score_values = {
            "audio": audio_activity,
            "scene_duration": duration_score,
            "scene_boundary": boundary_score,
        }
        if visual_samples:
            score_values["visual"] = visual_activity
        if transcript is not None:
            score_values["speech"] = min(1.0, dialogue_density / 0.5)
            score_values["dialogue_context"] = min(1.0, scene_speech_duration / 8.0)
        score = round(_weighted_score(score_values), 3)

        scene_id = f"scene_{index + 1:03d}"
        midpoint = round(start_time + scene_duration / 2.0, 2)
        thumb_filename = f"{project_id}_{scene_id}.jpg"
        extract_thumbnail(video_path, midpoint, THUMBNAILS_DIR / thumb_filename)

        summary_parts = [f"Moment {index + 1}", f"{scene_duration}s"]
        if dialogue_density >= 0.15 and transcript is not None:
            summary_parts.append("Speech")
        if visual_activity >= 0.5:
            summary_parts.append("Visual change")
        detected_scenes.append(DetectedScene(
            scene_id=scene_id,
            start_time=round(start_time, 2),
            end_time=round(end_time, 2),
            duration=scene_duration,
            thumbnail_url=f"/media/thumbnails/{thumb_filename}",
            score=score,
            audio_activity=round(audio_activity, 3),
            visual_activity=round(visual_activity, 3),
            dialogue_density=round(dialogue_density, 3),
            summary=" • ".join(summary_parts),
            selected=score >= 0.35,
        ))

        if progress_callback:
            progress_callback(
                90 + int(((index + 1) / max(total_scenes, 1)) * 9),
                f"Scoring scene {index + 1} of {total_scenes}...",
            )

    if progress_callback:
        progress_callback(100, f"Analysis complete. Identified {len(detected_scenes)} scenes.")
    return detected_scenes
