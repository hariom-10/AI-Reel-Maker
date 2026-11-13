import logging
import math
from pathlib import Path
from typing import Callable, List, Optional
from models import DetectedScene, ClipConfig, CropConfig, CaptionConfig, SubtitleItem
from services.transcriber import generate_captions_for_clip
from services.video_analyzer import extract_thumbnail
from config import THUMBNAILS_DIR

logger = logging.getLogger(__name__)

def generate_automatic_reels(
    scenes: List[DetectedScene],
    video_duration: float,
    video_path: Path,
    project_id: str,
    target_count: int = 5,
    target_duration: float = 30.0,
    aspect_ratio: str = "9:16",
    mode: str = "smart_crop",
    auto_captions: bool = True,
    caption_language: str = "en",
    caption_style: str = "bold_outline",
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> List[ClipConfig]:
    """
    Rank selected moments using audio-activity and scene-duration heuristics.
    Clip boundaries follow scene windows where possible; dialogue is not transcribed here.
    """
    if not scenes or video_duration <= 0:
        return []

    # Sort scenes by score in descending order
    sorted_scenes = sorted(scenes, key=lambda s: s.score, reverse=True)
    
    # Store candidate windows: (start_time, end_time, score, primary_scene_id)
    candidate_windows = []
    min_separation = max(10.0, target_duration * 0.6)

    for scene in sorted_scenes:
        if len(candidate_windows) >= target_count * 2:
            break

        # Check if this scene overlaps too much with already chosen windows
        overlap = False
        for cw in candidate_windows:
            if abs(scene.start_time - cw["start"]) < min_separation:
                overlap = True
                break
        if overlap:
            continue

        # Adjust window boundaries to match target_duration naturally
        scene_len = scene.duration
        if scene_len >= target_duration:
            # If scene is already long, pick the most active center section
            start = round(scene.start_time + (scene_len - target_duration) / 2.0, 2)
            end = round(min(video_duration, start + target_duration), 2)
        else:
            # Need to expand window to reach target_duration
            needed_expansion = target_duration - scene_len
            expand_before = needed_expansion / 2.0
            expand_after = needed_expansion / 2.0

            start = max(0.0, scene.start_time - expand_before)
            end = min(video_duration, scene.end_time + expand_after)

            # Re-adjust if hit 0 or video_duration
            if start == 0.0:
                end = min(video_duration, start + target_duration)
            elif end == video_duration:
                start = max(0.0, end - target_duration)

            start = round(start, 2)
            end = round(end, 2)

        actual_duration = round(end - start, 2)
        if actual_duration < 5.0:
            continue

        candidate_windows.append({
            "start": start,
            "end": end,
            "duration": actual_duration,
            "score": scene.score,
            "scene_id": scene.scene_id
        })

    # Sort final candidate windows chronologically
    candidate_windows = sorted(candidate_windows[:target_count], key=lambda c: c["start"])

    clips: List[ClipConfig] = []
    for idx, cw in enumerate(candidate_windows, 1):
        if progress_callback:
            progress_callback(
                int(((idx - 1) / len(candidate_windows)) * 100),
                f"Preparing clip {idx} of {len(candidate_windows)}...",
            )
        clip_id = f"reel_{idx:02d}"
        title = f"Suggested Short #{idx} ({cw['duration']}s)"

        crop_config = CropConfig(
            aspect_ratio=aspect_ratio,
            mode=mode,
            center_x_percent=50.0,
            blur_strength=25
        )

        caption_config = CaptionConfig(
            enabled=auto_captions,
            language=caption_language,
            style=caption_style,
            font_family="Impact",
            font_size=24,
            text_color="#FFD700" if caption_style == "bold_outline" else "#FFFFFF",
            position="bottom",
            y_percent=80
        )

        subtitles = []
        if auto_captions:
            subtitles = generate_captions_for_clip(
                start_time=cw["start"],
                end_time=cw["end"],
                language=caption_language,
                video_path=video_path
            )

        # Generate thumbnail for reel
        mid = round(cw["start"] + (cw["duration"] / 2), 2)
        thumb_name = f"{project_id}_{clip_id}.jpg"
        thumb_path = THUMBNAILS_DIR / thumb_name
        extract_thumbnail(video_path, mid, thumb_path)

        clips.append(ClipConfig(
            clip_id=clip_id,
            title=title,
            start_time=cw["start"],
            end_time=cw["end"],
            duration=cw["duration"],
            score=cw["score"],
            thumbnail_url=f"/media/thumbnails/{thumb_name}",
            crop_config=crop_config,
            caption_config=caption_config,
            subtitles=subtitles,
            status="ready"
        ))
        if progress_callback:
            progress_callback(
                int((idx / len(candidate_windows)) * 100),
                f"Prepared clip {idx} of {len(candidate_windows)}.",
            )

    return clips
