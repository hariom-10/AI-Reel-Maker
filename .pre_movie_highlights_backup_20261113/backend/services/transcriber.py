import importlib.util
import logging
import subprocess
import uuid
from pathlib import Path
from typing import List, Optional

from config import FFMPEG_BIN, TEMP_DIR
from models import CaptionConfig, SubtitleItem

logger = logging.getLogger(__name__)
_whisper_model = None


def whisper_available() -> bool:
    return importlib.util.find_spec("whisper") is not None


def transcribe_audio_whisper(
    audio_path: Path,
    language: str = "en",
    clip_start_time: float = 0.0,
) -> Optional[List[SubtitleItem]]:
    """Transcribe with a locally installed Whisper model; never invent captions."""
    global _whisper_model
    try:
        import whisper

        if _whisper_model is None:
            logger.info("Loading local Whisper base model for transcription.")
            _whisper_model = whisper.load_model("base")

        lang_code = "hi" if language == "hi" else "en"
        result = _whisper_model.transcribe(
            str(audio_path),
            language=lang_code if language != "hinglish" else None,
            fp16=False,
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


def generate_captions_for_clip(
    start_time: float,
    end_time: float,
    language: str = "en",
    video_path: Optional[Path] = None,
) -> List[SubtitleItem]:
    """Create real local captions when Whisper is installed; otherwise return none."""
    if not video_path or end_time <= start_time:
        return []
    if not whisper_available():
        logger.warning("Auto captions skipped: install the optional openai-whisper package.")
        return []

    audio_path = TEMP_DIR / f"caption_{uuid.uuid4().hex}.wav"
    command = [
        FFMPEG_BIN,
        "-y",
        "-ss",
        str(start_time),
        "-t",
        str(end_time - start_time),
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
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
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    else:
        r, g, b = "FF", "FF", "FF"
    alpha = int((1.0 - opacity) * 255)
    return f"&H{alpha:02X}{b}{g}{r}"


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
        rel_start = max(0.0, subtitle.start_time - clip_start_time)
        rel_end = max(rel_start + 0.3, subtitle.end_time - clip_start_time)
        text = subtitle.text.upper() if config.style in ["bold_outline", "karaoke"] else subtitle.text
        text = text.replace("\n", "\\N")
        events.append(
            f"Dialogue: 0,{format_timestamp_ass(rel_start)},"
            f"{format_timestamp_ass(rel_end)},Default,,0,0,0,,{text}"
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
    for idx, subtitle in enumerate(subtitles, 1):
        rel_start = max(0.0, subtitle.start_time - clip_start_time)
        rel_end = max(rel_start + 0.3, subtitle.end_time - clip_start_time)
        lines.extend(
            [
                str(idx),
                f"{format_timestamp_srt(rel_start)} --> {format_timestamp_srt(rel_end)}",
                subtitle.text.strip(),
                "",
            ]
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
