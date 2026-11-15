import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from config import THUMBNAILS_DIR
from models import CaptionConfig, ClipConfig, CropConfig, DetectedScene, SubtitleItem
from services.transcriber import generate_captions_for_clip
from services.video_analyzer import HIGHLIGHT_SCORING_WEIGHTS, extract_thumbnail

logger = logging.getLogger(__name__)
SCENE_BOUNDARY_SNAP_SECONDS = 3.0
MIN_CLIP_DURATION_SECONDS = 5.0
MIN_NON_OVERLAP_RATIO = 0.65


def _speech_clusters(
    scene: DetectedScene,
    transcript: List[SubtitleItem],
) -> List[Tuple[float, float]]:
    segments = sorted(
        (
            (max(scene.start_time, item.start_time), min(scene.end_time, item.end_time))
            for item in transcript
            if item.end_time > scene.start_time and item.start_time < scene.end_time
        ),
        key=lambda interval: interval[0],
    )
    clusters: List[Tuple[float, float]] = []
    for start, end in segments:
        if end <= start:
            continue
        if clusters and start <= clusters[-1][1] + 1.25:
            clusters[-1] = (clusters[-1][0], max(clusters[-1][1], end))
        else:
            clusters.append((start, end))
    return clusters


def _candidate_anchors(
    scenes: List[DetectedScene],
    transcript: Optional[List[SubtitleItem]],
    target_duration: float,
) -> List[Tuple[float, Optional[Tuple[float, float]]]]:
    anchors: List[Tuple[float, Optional[Tuple[float, float]]]] = []
    for scene in scenes:
        clusters = _speech_clusters(scene, transcript or [])
        if clusters:
            for cluster_start, cluster_end in clusters:
                span = cluster_end - cluster_start
                if span <= target_duration:
                    anchors.append(((cluster_start + cluster_end) / 2.0, (cluster_start, cluster_end)))
                else:
                    anchor = cluster_start + target_duration / 2.0
                    while anchor < cluster_end:
                        anchors.append((anchor, (cluster_start, cluster_end)))
                        anchor += target_duration * 0.75
        elif scene.duration > target_duration:
            anchor = scene.start_time + target_duration / 2.0
            while anchor < scene.end_time:
                anchors.append((anchor, None))
                anchor += target_duration * 0.75
        else:
            anchors.append(((scene.start_time + scene.end_time) / 2.0, None))
    return anchors


def _fit_clip_window(
    anchor: float,
    speech_span: Optional[Tuple[float, float]],
    boundaries: List[float],
    video_duration: float,
    target_duration: float,
) -> Tuple[float, float]:
    actual_duration = min(target_duration, video_duration)
    maximum_start = max(0.0, video_duration - actual_duration)
    start = min(maximum_start, max(0.0, anchor - actual_duration / 2.0))

    if speech_span:
        speech_start, speech_end = speech_span
        earliest = max(0.0, speech_end + 1.0 - actual_duration)
        latest = min(maximum_start, speech_start - 1.0)
        if earliest <= latest:
            start = min(latest, max(earliest, start))

    end = start + actual_duration
    start_candidates = [
        boundary for boundary in boundaries
        if abs(boundary - start) <= SCENE_BOUNDARY_SNAP_SECONDS
        and (not speech_span or boundary <= speech_span[0] - 0.25)
    ]
    end_candidates = [
        boundary for boundary in boundaries
        if abs(boundary - end) <= SCENE_BOUNDARY_SNAP_SECONDS
        and (not speech_span or boundary >= speech_span[1] + 0.25)
    ]

    best_pair = None
    best_distance = float("inf")
    for candidate_start in start_candidates:
        for candidate_end in end_candidates:
            candidate_duration = candidate_end - candidate_start
            if not MIN_CLIP_DURATION_SECONDS <= candidate_duration <= video_duration:
                continue
            if not 0.75 * target_duration <= candidate_duration <= 1.25 * target_duration:
                continue
            distance = abs(candidate_start - start) + abs(candidate_end - end)
            if distance < best_distance:
                best_pair = (candidate_start, candidate_end)
                best_distance = distance
    if best_pair:
        start, end = best_pair
    else:
        end = start + actual_duration
    return round(max(0.0, start), 2), round(min(video_duration, end), 2)


def _weighted_scene_metric(
    start: float,
    end: float,
    scenes: List[DetectedScene],
    attribute: str,
) -> float:
    weighted_value = 0.0
    total_overlap = 0.0
    for scene in scenes:
        overlap = max(0.0, min(end, scene.end_time) - max(start, scene.start_time))
        if overlap:
            weighted_value += overlap * float(getattr(scene, attribute))
            total_overlap += overlap
    return weighted_value / total_overlap if total_overlap else 0.0


def _overlap_duration(start: float, end: float, transcript: List[SubtitleItem]) -> float:
    return sum(
        max(0.0, min(end, item.end_time) - max(start, item.start_time))
        for item in transcript
    )


def _candidate_score(
    start: float,
    end: float,
    scenes: List[DetectedScene],
    transcript: Optional[List[SubtitleItem]],
    speech_span: Optional[Tuple[float, float]],
    target_duration: float,
    boundaries: List[float],
) -> float:
    clip_duration = end - start
    duration_fit = max(0.0, 1.0 - abs(clip_duration - target_duration) / max(target_duration, 1.0))
    start_distance = min((abs(start - boundary) for boundary in boundaries), default=target_duration)
    end_distance = min((abs(end - boundary) for boundary in boundaries), default=target_duration)
    boundary_fit = (
        max(0.0, 1.0 - start_distance / SCENE_BOUNDARY_SNAP_SECONDS)
        + max(0.0, 1.0 - end_distance / SCENE_BOUNDARY_SNAP_SECONDS)
    ) / 2.0
    score_values = {
        "audio": _weighted_scene_metric(start, end, scenes, "audio_activity"),
        "scene_duration": duration_fit,
        "scene_boundary": boundary_fit,
    }
    if any(scene.visual_activity > 0.0 for scene in scenes):
        score_values["visual"] = _weighted_scene_metric(
            start,
            end,
            scenes,
            "visual_activity",
        )

    if transcript is not None:
        speech_duration = _overlap_duration(start, end, transcript)
        score_values["speech"] = min(1.0, speech_duration / max(1.0, target_duration * 0.25))
        if speech_span:
            before_context = max(0.0, speech_span[0] - start)
            after_context = max(0.0, end - speech_span[1])
            score_values["dialogue_context"] = min(1.0, before_context / 1.5) * min(
                1.0, after_context / 1.5
            )
        else:
            score_values["dialogue_context"] = 0.0

    total_weight = sum(HIGHLIGHT_SCORING_WEIGHTS[key] for key in score_values)
    return sum(
        HIGHLIGHT_SCORING_WEIGHTS[key] * value
        for key, value in score_values.items()
    ) / total_weight if total_weight else 0.0


def _overlaps_heavily(candidate: Dict[str, float], chosen: List[Dict[str, float]]) -> bool:
    candidate_duration = candidate["end"] - candidate["start"]
    for item in chosen:
        overlap = max(
            0.0,
            min(candidate["end"], item["end"]) - max(candidate["start"], item["start"]),
        )
        shorter_duration = min(candidate_duration, item["end"] - item["start"])
        if shorter_duration and overlap / shorter_duration > 1.0 - MIN_NON_OVERLAP_RATIO:
            return True
    return False


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
    transcript: Optional[List[SubtitleItem]] = None,
) -> List[ClipConfig]:
    """Rank distinct clip windows from speech, activity, scene boundaries, and context."""
    if not scenes or video_duration <= 0 or target_count <= 0:
        return []
    target_duration = max(MIN_CLIP_DURATION_SECONDS, min(120.0, target_duration))

    boundaries = sorted({
        0.0,
        video_duration,
        *(
            boundary
            for scene in scenes
            for boundary in (scene.start_time, scene.end_time)
            if 0.0 <= boundary <= video_duration
        ),
    })
    candidates = []
    for anchor, speech_span in _candidate_anchors(scenes, transcript, target_duration):
        start, end = _fit_clip_window(
            anchor,
            speech_span,
            boundaries,
            video_duration,
            target_duration,
        )
        if end - start < MIN_CLIP_DURATION_SECONDS:
            continue
        candidates.append({
            "start": start,
            "end": end,
            "score": _candidate_score(
                start,
                end,
                scenes,
                transcript,
                speech_span,
                target_duration,
                boundaries,
            ),
        })

    candidates.sort(key=lambda candidate: (-candidate["score"], candidate["start"]))
    chosen: List[Dict[str, float]] = []
    for candidate in candidates:
        if not _overlaps_heavily(candidate, chosen):
            chosen.append(candidate)
        if len(chosen) >= target_count:
            break
    chosen.sort(key=lambda candidate: candidate["start"])

    clips: List[ClipConfig] = []
    for index, candidate in enumerate(chosen, 1):
        if progress_callback:
            progress_callback(
                int(((index - 1) / max(len(chosen), 1)) * 100),
                f"Preparing reel candidate {index} of {len(chosen)}...",
            )
        clip_duration = round(candidate["end"] - candidate["start"], 2)
        clip_id = f"reel_{index:02d}"
        crop_config = CropConfig(
            aspect_ratio=aspect_ratio,
            mode=mode,
            center_x_percent=50.0,
            blur_strength=25,
        )
        caption_config = CaptionConfig(
            enabled=auto_captions,
            language=caption_language,
            style=caption_style,
            font_family="Impact",
            font_size=24,
            text_color="#FFD700" if caption_style == "bold_outline" else "#FFFFFF",
            position="bottom",
            y_percent=80,
        )

        if transcript is None:
            subtitles = (
                generate_captions_for_clip(
                    start_time=candidate["start"],
                    end_time=candidate["end"],
                    language=caption_language,
                    video_path=video_path,
                )
                if auto_captions
                else []
            )
        else:
            subtitles = [
                item for item in transcript
                if item.end_time > candidate["start"] and item.start_time < candidate["end"]
            ] if auto_captions else []

        thumbnail_name = f"{project_id}_{clip_id}.jpg"
        extract_thumbnail(
            video_path,
            round(candidate["start"] + clip_duration / 2.0, 2),
            THUMBNAILS_DIR / thumbnail_name,
        )
        clips.append(ClipConfig(
            clip_id=clip_id,
            title=f"Suggested Moment #{index} ({clip_duration}s)",
            start_time=candidate["start"],
            end_time=candidate["end"],
            duration=clip_duration,
            score=round(candidate["score"], 3),
            thumbnail_url=f"/media/thumbnails/{thumbnail_name}",
            crop_config=crop_config,
            caption_config=caption_config,
            subtitles=subtitles,
            status="ready",
        ))
        if progress_callback:
            progress_callback(
                int((index / max(len(chosen), 1)) * 100),
                f"Prepared reel candidate {index} of {len(chosen)}.",
            )
    return clips
