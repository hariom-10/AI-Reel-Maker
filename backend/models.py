from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class VideoMetadata(BaseModel):
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 30.0
    bitrate: int = 0
    codec: str = "h264"
    format_name: str = "mp4"
    size_bytes: int = 0

class DetectedScene(BaseModel):
    scene_id: str
    start_time: float
    end_time: float
    duration: float
    thumbnail_url: str = ""
    score: float = 0.5
    audio_activity: float = 0.5
    visual_activity: float = 0.5
    dialogue_density: float = 0.5
    summary: str = ""
    selected: bool = True

class SubtitleItem(BaseModel):
    id: str
    start_time: float
    end_time: float
    text: str

class CaptionConfig(BaseModel):
    enabled: bool = True
    language: str = "en"  # "en", "hi", "hinglish"
    font_family: str = "Impact"
    font_size: int = 24
    text_color: str = "#FFD700"  # Vibrant gold / yellow
    bg_color: str = "#000000"
    bg_opacity: float = 0.6
    position: str = "bottom"  # "bottom", "center", "top", "custom"
    y_percent: int = 80
    style: str = "bold_outline"  # "bold_outline", "clean_pill", "karaoke", "classic"

class BlurRegion(BaseModel):
    x: float = 0.0  # percentage 0-100
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

class CropConfig(BaseModel):
    aspect_ratio: str = "9:16"  # "9:16", "16:9", "1:1"
    mode: str = "smart_crop"    # "smart_crop", "blur_bg", "fit"
    center_x_percent: float = 50.0
    blur_strength: int = 25
    blur_region: Optional[BlurRegion] = None

class ClipConfig(BaseModel):
    clip_id: str
    title: str = "Reel Clip"
    start_time: float
    end_time: float
    duration: float
    score: float = 0.8
    thumbnail_url: str = ""
    crop_config: CropConfig = Field(default_factory=CropConfig)
    caption_config: CaptionConfig = Field(default_factory=CaptionConfig)
    subtitles: List[SubtitleItem] = Field(default_factory=list)
    status: str = "ready"  # "ready", "rendering", "exported", "error"
    output_url: str = ""
    output_path: str = ""
    error_message: str = ""

class Project(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    video_filename: str
    video_path: str
    video_url: str
    metadata: VideoMetadata = Field(default_factory=VideoMetadata)
    scenes: List[DetectedScene] = Field(default_factory=list)
    clips: List[ClipConfig] = Field(default_factory=list)
    status: str = "uploaded"  # "uploaded", "analyzing", "ready", "exporting", "completed"
    progress: int = 0
    status_message: str = "Ready"

class GenerateReelsRequest(BaseModel):
    clip_duration: float = 30.0  # 15, 30, 45, 60 or custom
    target_count: int = 5
    aspect_ratio: str = "9:16"
    mode: str = "smart_crop"
    auto_captions: bool = True
    caption_language: str = "en"
    caption_style: str = "bold_outline"

class ExportRequest(BaseModel):
    clip_ids: List[str]
    quality: str = "high"
    fps: int = 30
    resolution: str = "1080x1920"

class RenameProjectRequest(BaseModel):
    name: str
