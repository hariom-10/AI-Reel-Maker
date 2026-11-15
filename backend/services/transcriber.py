import hashlib
import importlib
import importlib.util
import json
import logging
import math
import os
import re
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Callable, List, Optional

from config import FFMPEG_BIN, FFPROBE_BIN, TEMP_DIR, TRANSCRIPTS_DIR
from models import CaptionConfig, SubtitleItem
from services.ffmpeg_runner import run_ffmpeg

logger = logging.getLogger(__name__)

WHISPER_MODEL_NAME = "base"
TRANSCRIPTION_CHUNK_SECONDS = 30.0
TRANSCRIPTION_OVERLAP_SECONDS = 1.0
_whisper_model = None
_model_lock = threading.Lock()
_transcription_lock = threading.Lock()
_video_transcription_lock = threading.Lock()


def _whisper_model_path() -> Path:
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return cache_root / "whisper" / f"{WHISPER_MODEL_NAME}.pt"


def whisper_available() -> bool:
    """Return true only when the package and local Base weights are already present."""
    return (
        importlib.util.find_spec("whisper") is not None
        and _whisper_model_path().is_file()
    )


def _get_whisper_model():
    global _whisper_model
    with _model_lock:
        if _whisper_model is None:
            if importlib.util.find_spec("whisper") is None:
                raise RuntimeError("The optional openai-whisper package is not installed.")
            model_path = _whisper_model_path()
            if not model_path.is_file():
                raise RuntimeError(
                    f"Local Whisper Base weights were not found at {model_path}; "
                    "automatic model downloads are disabled."
                )
            logger.info("Loading local Whisper Base model from %s.", model_path)
            load_model = getattr(importlib.import_module("whisper"), "load_model", None)
            if load_model is None:
                raise RuntimeError("The installed whisper package does not provide load_model.")
            _whisper_model = load_model(str(model_path), device="cpu")
        return _whisper_model


def transcribe_audio_whisper(
    audio_path: Path,
    language: str = "en",
    clip_start_time: float = 0.0,
) -> Optional[List[SubtitleItem]]:
    """Transcribe with local Whisper; never download weights or invent captions."""
    try:
        model = _get_whisper_model()
        language_code = "hi" if language == "hi" else "en"
        result_language = None if language in {"hinglish", "auto"} else language_code
        with _transcription_lock:
            result = model.transcribe(
                str(audio_path),
                language=result_language,
                fp16=False,
                condition_on_previous_text=False,
                verbose=False,
            )
        return [
            SubtitleItem(
                id=f"sub_{idx}",
                start_time=round(clip_start_time + float(segment["start"]), 2),
                end_time=round(clip_start_time + float(segment["end"]), 2),
                text=str(segment.get("text", "")).strip(),
            )
            for idx, segment in enumerate(result.get("segments", []), 1)
            if str(segment.get("text", "")).strip()
        ]
    except Exception as exc:
        logger.warning("Whisper transcription unavailable: %s", exc)
        return None


def _cache_signature(video_path: Path, duration: float, language: Optional[str]) -> str:
    stat = video_path.stat()
    identity = "|".join((
        str(video_path.resolve()),
        str(stat.st_size),
        str(stat.st_mtime_ns),
        f"{duration:.3f}",
        language or "auto",
        WHISPER_MODEL_NAME,
    ))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _cache_path(project_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", project_id).strip("._")
    if not safe_id:
        raise ValueError("A valid project ID is required for transcript caching.")
    return TRANSCRIPTS_DIR / f"{safe_id}.json"


def load_cached_transcript(
    video_path: Path,
    project_id: str,
    duration: float,
    language: Optional[str] = None,
) -> Optional[List[SubtitleItem]]:
    """Load a transcript only when it matches the current video and model settings."""
    try:
        cache_path = _cache_path(project_id)
        if not cache_path.is_file():
            return None
        signature = _cache_signature(video_path, duration, language)
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if cache.get("signature") != signature or not isinstance(cache.get("segments"), list):
            return None
        return [SubtitleItem(**segment) for segment in cache["segments"]]
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Could not read transcript cache for %s: %s", project_id, exc)
        return None


def _save_cached_transcript(
    video_path: Path,
    project_id: str,
    duration: float,
    language: Optional[str],
    subtitles: List[SubtitleItem],
) -> None:
    cache_path = _cache_path(project_id)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    signature = _cache_signature(video_path, duration, language)
    payload = {
        "version": 1,
        "signature": signature,
        "segments": [
            {
                "id": item.id,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "text": item.text,
            }
            for item in subtitles
        ],
    }
    temporary_path = cache_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary_path.replace(cache_path)


def _video_has_audio(video_path: Path) -> bool:
    result = subprocess.run(
        [
            FFPROBE_BIN,
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(video_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def transcribe_video(
    video_path: Path,
    project_id: str,
    duration: float,
    language: Optional[str] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Optional[List[SubtitleItem]]:
    """Transcribe long video in short audio chunks and cache absolute timestamps."""
    if duration <= 0 or not video_path.is_file():
        raise ValueError("A readable video and positive duration are required for transcription.")

    cached = load_cached_transcript(video_path, project_id, duration, language)
    if cached is not None:
        if progress_callback:
            progress_callback(100, "Using cached full-video transcript.")
        return cached
    if not whisper_available():
        return None

    with _video_transcription_lock:
        cached = load_cached_transcript(video_path, project_id, duration, language)
        if cached is not None:
            if progress_callback:
                progress_callback(100, "Using cached full-video transcript.")
            return cached

        if not _video_has_audio(video_path):
            _save_cached_transcript(video_path, project_id, duration, language, [])
            if progress_callback:
                progress_callback(100, "No audio stream found; speech transcription was skipped.")
            return []

        chunks = math.ceil(duration / TRANSCRIPTION_CHUNK_SECONDS)
        subtitles: List[SubtitleItem] = []
        with tempfile.TemporaryDirectory(prefix="transcribe_", dir=TEMP_DIR) as temporary_dir:
            for chunk_index in range(chunks):
                core_start = chunk_index * TRANSCRIPTION_CHUNK_SECONDS
                core_end = min(duration, core_start + TRANSCRIPTION_CHUNK_SECONDS)
                extract_start = max(0.0, core_start - TRANSCRIPTION_OVERLAP_SECONDS)
                extract_end = min(duration, core_end + TRANSCRIPTION_OVERLAP_SECONDS)
                audio_path = Path(temporary_dir) / f"chunk_{chunk_index:05d}.wav"
                command = [
                    FFMPEG_BIN,
                    "-y",
                    "-ss", str(extract_start),
                    "-t", str(extract_end - extract_start),
                    "-i", str(video_path),
                    "-vn",
                    "-ac", "1",
                    "-ar", "16000",
                    "-c:a", "pcm_s16le",
                    str(audio_path),
                ]

                def extraction_progress(percent: int, _message: str):
                    if progress_callback:
                        overall = int(((chunk_index + percent / 100.0) / chunks) * 100)
                        progress_callback(
                            min(99, overall),
                            f"Extracting transcription audio chunk {chunk_index + 1} of {chunks}...",
                        )

                try:
                    run_ffmpeg(
                        command,
                        extract_end - extract_start,
                        extraction_progress,
                    )
                    if not audio_path.is_file() or audio_path.stat().st_size <= 44:
                        raise RuntimeError(f"FFmpeg produced no audio for chunk {chunk_index + 1}.")

                    chunk_subtitles = transcribe_audio_whisper(
                        audio_path,
                        language or "auto",
                        extract_start,
                    )
                    if chunk_subtitles is None:
                        raise RuntimeError(f"Whisper failed to transcribe chunk {chunk_index + 1}.")

                    for subtitle in chunk_subtitles:
                        midpoint = (subtitle.start_time + subtitle.end_time) / 2.0
                        if core_start <= midpoint < core_end or (
                            chunk_index == chunks - 1 and midpoint == duration
                        ):
                            start_time = max(0.0, min(duration, subtitle.start_time))
                            end_time = max(start_time, min(duration, subtitle.end_time))
                            if end_time > start_time:
                                subtitles.append(SubtitleItem(
                                    id=f"sub_{len(subtitles) + 1}",
                                    start_time=start_time,
                                    end_time=end_time,
                                    text=subtitle.text,
                                ))
                finally:
                    audio_path.unlink(missing_ok=True)

                if progress_callback:
                    progress_callback(
                        int(((chunk_index + 1) / chunks) * 100),
                        f"Transcribed audio chunk {chunk_index + 1} of {chunks}.",
                    )

        subtitles.sort(key=lambda item: (item.start_time, item.end_time))
        _save_cached_transcript(video_path, project_id, duration, language, subtitles)
        if progress_callback:
            progress_callback(100, f"Full-video transcription complete: {len(subtitles)} speech segments.")
        return subtitles


def generate_captions_for_clip(
    start_time: float,
    end_time: float,
    language: str = "en",
    video_path: Optional[Path] = None,
) -> List[SubtitleItem]:
    """Create real local captions when Whisper Base is already available."""
    if not video_path or end_time <= start_time:
        return []
    if not whisper_available():
        logger.info("Auto captions skipped: local Whisper Base package or weights are unavailable.")
        return []

    audio_path = TEMP_DIR / f"caption_{uuid.uuid4().hex}.wav"
    command = [
        FFMPEG_BIN,
        "-y",
        "-ss", str(start_time),
        "-t", str(end_time - start_time),
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(audio_path),
    ]
    try:
        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return transcribe_audio_whisper(audio_path, language, start_time) or []
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("Could not extract audio for captions from %s: %s", video_path, exc)
        return []
    finally:
        audio_path.unlink(missing_ok=True)


def format_timestamp_ass(seconds: float) -> str:
    """Format seconds as H:MM:SS.CC for ASS subtitles."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds as HH:MM:SS,mmm for SRT subtitles."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def hex_to_ass_color(hex_color: str, opacity: float = 1.0) -> str:
    """Convert #RRGGBB to &HAABBGGRR (ASS color format)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        red, green, blue = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    else:
        red, green, blue = "FF", "FF", "FF"
    alpha = int((1.0 - opacity) * 255)
    return f"&H{alpha:02X}{blue}{green}{red}"


def generate_ass_subtitle_file(
    subtitles: List[SubtitleItem],
    config: CaptionConfig,
    clip_start_time: float,
    output_path: Path,
    target_width: int = 1080,
    target_height: int = 1920,
) -> Path:
    """Generate a styled ASS subtitle file for FFmpeg burning."""
    font_name = config.font_family if config.font_family else "Impact"
    font_size = max(18, int(config.font_size * (target_height / 1080)))
    primary_color = hex_to_ass_color(config.text_color, 1.0)
    outline_color = "&H00000000"
    back_color = hex_to_ass_color(config.bg_color, config.bg_opacity)

    alignment = 2
    margin_v = int(target_height * 0.18)
    if config.position == "center":
        alignment = 5
        margin_v = 0
    elif config.position == "top":
        alignment = 8
        margin_v = int(target_height * 0.12)
    elif config.position == "custom":
        alignment = 2
        margin_v = max(20, int(target_height * (1.0 - (config.y_percent / 100.0))))

    border_style = 3 if config.style == "clean_pill" else 1
    outline_thickness = 4 if config.style == "bold_outline" else 2
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target_width}
PlayResY: {target_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,100,100,1,0,{border_style},{outline_thickness},2,{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for subtitle in subtitles:
        relative_start = max(0.0, subtitle.start_time - clip_start_time)
        relative_end = max(relative_start + 0.3, subtitle.end_time - clip_start_time)
        text = subtitle.text.upper() if config.style in ["bold_outline", "karaoke"] else subtitle.text
        text = text.replace("\n", "\\N")
        events.append(
            f"Dialogue: 0,{format_timestamp_ass(relative_start)},"
            f"{format_timestamp_ass(relative_end)},Default,,0,0,0,,{text}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return output_path


def generate_srt_subtitle_file(
    subtitles: List[SubtitleItem],
    clip_start_time: float,
    output_path: Path,
) -> Path:
    """Generate standard SRT subtitles."""
    lines = []
    for index, subtitle in enumerate(subtitles, 1):
        relative_start = max(0.0, subtitle.start_time - clip_start_time)
        relative_end = max(relative_start + 0.3, subtitle.end_time - clip_start_time)
        lines.extend([
            str(index),
            f"{format_timestamp_srt(relative_start)} --> {format_timestamp_srt(relative_end)}",
            subtitle.text.strip(),
            "",
        ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
