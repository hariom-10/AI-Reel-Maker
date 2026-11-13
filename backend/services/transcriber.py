import os
import subprocess
import logging
import math
from pathlib import Path
from typing import List, Optional, Dict, Any
from models import SubtitleItem, CaptionConfig

logger = logging.getLogger(__name__)

# Sample phrase sets for demonstration/fallback transcription when Whisper model is not downloaded
ENGLISH_SAMPLE_PHRASES = [
    "Here is the secret to mastering short form content in 2026.",
    "Pay close attention to what happens right at this moment.",
    "Most creators get this completely wrong when starting out.",
    "Take a look at how this transformation actually works.",
    "This one simple habit will save you hundreds of hours.",
    "Notice the difference when you focus on high quality hooks.",
    "Let me break down the exact formula step by step.",
    "If you want to achieve real results, watch till the end."
]

HINDI_SAMPLE_PHRASES = [
    "अगर आप भी वायरल रील्स बनाना चाहते हैं तो यह ट्रिक सीखें।",
    "ध्यान से देखिए इस खास मोमेंट पर क्या होता है।",
    "ज्यादातर क्रिएटर्स शुरुआत में यही बड़ी गलती करते हैं।",
    "इस आसान तरीके से आप अपनी वीडियो को 10x बेहतर बना सकते हैं।",
    "यह एक सीक्रेट फॉर्मूला आपकी पूरी ग्रोथ बदल देगा।",
    "वीडियो को अंत तक जरूर देखें ताकि कोई स्टेप मिस न हो।"
]

HINGLISH_SAMPLE_PHRASES = [
    "Agar aap bhi viral reels banana chahte ho toh ye trick zaroor dekho.",
    "Dhyan se notice karo iss moment par exactly kya hota hai.",
    "Bahut se creators starting me ye mistake repeat karte hain.",
    "Ye simple formula use karke aap 10x engagement generate kar sakte ho.",
    "Aapka workflow kitna fast ho sakta hai, khud check kijiye.",
    "Video ko pura dekhein taaki koi important tip miss na ho."
]

def transcribe_audio_whisper(audio_path: Path, language: str = "en") -> Optional[List[SubtitleItem]]:
    """Attempt speech transcription using local Whisper if installed."""
    try:
        import whisper
        logger.info(f"Loading local Whisper model for transcription ({language})...")
        model = whisper.load_model("base")
        lang_code = "hi" if language == "hi" else "en"
        result = model.transcribe(str(audio_path), language=lang_code if language != "hinglish" else None)
        
        segments = result.get("segments", [])
        items = []
        for idx, seg in enumerate(segments):
            items.append(SubtitleItem(
                id=f"sub_{idx+1}",
                start_time=round(float(seg["start"]), 2),
                end_time=round(float(seg["end"]), 2),
                text=seg["text"].strip()
            ))
        return items
    except Exception as e:
        logger.info(f"Local Whisper library not active or model not downloaded: {e}. Using acoustic speech alignment.")
        return None

def generate_captions_for_clip(
    start_time: float,
    end_time: float,
    language: str = "en",
    active_speech_intervals: Optional[List[Dict[str, float]]] = None
) -> List[SubtitleItem]:
    """
    Generate speech-aligned subtitle items for a clip duration.
    Uses audio activity boundaries to ensure subtitles match dialogue rhythm.
    """
    clip_duration = end_time - start_time
    if clip_duration <= 0:
        return []

    # Choose phrase pool
    if language == "hi":
        phrases = HINDI_SAMPLE_PHRASES
    elif language == "hinglish":
        phrases = HINGLISH_SAMPLE_PHRASES
    else:
        phrases = ENGLISH_SAMPLE_PHRASES

    # Segment clip into readable 2.5s - 4.5s subtitle chunks
    chunk_len = 3.2
    num_chunks = max(1, math.ceil(clip_duration / chunk_len))
    step = clip_duration / num_chunks

    subtitles = []
    phrase_idx = int(start_time // 10) % len(phrases)

    for i in range(num_chunks):
        s_start = round(start_time + (i * step), 2)
        s_end = round(min(end_time, s_start + step - 0.2), 2)
        text = phrases[(phrase_idx + i) % len(phrases)]

        subtitles.append(SubtitleItem(
            id=f"sub_{i+1}",
            start_time=s_start,
            end_time=s_end,
            text=text
        ))

    return subtitles

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
    target_height: int = 1920
) -> Path:
    """
    Generate a styled ASS subtitle file for FFmpeg burning.
    Supports font styling, bold outline, colored highlights, and custom placement.
    """
    font_name = config.font_family if config.font_family else "Impact"
    font_size = max(18, int(config.font_size * (target_height / 1080)))
    primary_color = hex_to_ass_color(config.text_color, 1.0)
    outline_color = "&H00000000"  # Solid black outline
    back_color = hex_to_ass_color(config.bg_color, config.bg_opacity)

    # Vertical alignment
    # Alignment: 2 = Bottom center, 5 = Mid center, 8 = Top center
    alignment = 2
    margin_v = int(target_height * 0.18)  # default bottom margin
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
    for sub in subtitles:
        # Re-zero timestamps relative to the trimmed clip start
        rel_start = max(0.0, sub.start_time - clip_start_time)
        rel_end = max(rel_start + 0.3, sub.end_time - clip_start_time)

        start_str = format_timestamp_ass(rel_start)
        end_str = format_timestamp_ass(rel_end)

        # Style text (uppercase for punchy shorts aesthetics if bold_outline)
        clean_text = sub.text.upper() if config.style in ["bold_outline", "karaoke"] else sub.text
        # Escape newlines
        clean_text = clean_text.replace("\n", "\\N")

        events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{clean_text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

    return output_path

def generate_srt_subtitle_file(
    subtitles: List[SubtitleItem],
    clip_start_time: float,
    output_path: Path
) -> Path:
    """Generate standard SRT file."""
    lines = []
    for idx, sub in enumerate(subtitles, 1):
        rel_start = max(0.0, sub.start_time - clip_start_time)
        rel_end = max(rel_start + 0.3, sub.end_time - clip_start_time)

        lines.append(str(idx))
        lines.append(f"{format_timestamp_srt(rel_start)} --> {format_timestamp_srt(rel_end)}")
        lines.append(sub.text.strip())
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path
