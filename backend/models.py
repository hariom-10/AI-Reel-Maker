from typing import List, Literal, Optional, Dict, Any
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
    x: float = Field(default=0.0, ge=0, le=100, allow_inf_nan=False)
    y: float = Field(default=0.0, ge=0, le=100, allow_inf_nan=False)
    width: float = Field(default=0.0, ge=0, le=100, allow_inf_nan=False)
    height: float = Field(default=0.0, ge=0, le=100, allow_inf_nan=False)

class CropConfig(BaseModel):
    aspect_ratio: str = "9:16"  # "9:16", "16:9", "1:1"
    mode: str = "smart_crop"    # "smart_crop", "blur_bg", "fit"
    center_x_percent: float = Field(default=50.0, ge=0, le=100, allow_inf_nan=False)
    blur_strength: int = Field(default=25, ge=1, le=100)
    blur_region: Optional[BlurRegion] = None

class ClipConfig(BaseModel):
    clip_id: str
    title: str = "Reel Clip"
    start_time: float = Field(ge=0, allow_inf_nan=False)
    end_time: float = Field(gt=0, allow_inf_nan=False)
    duration: float = Field(gt=0, allow_inf_nan=False)
    score: float = 0.8
    thumbnail_url: str = ""
    crop_config: CropConfig = Field(default_factory=CropConfig)
    caption_config: CaptionConfig = Field(default_factory=CaptionConfig)
    subtitles: List[SubtitleItem] = Field(default_factory=list)
    status: str = "ready"  # "ready", "rendering", "exported", "error"
    output_url: str = ""
    output_path: str = ""
    error_message: str = ""

class CleanupRegion(BaseModel):
    id: str
    type: Literal["inpaint", "blur", "replace_logo", "add_text"] = "inpaint"
    x: float = Field(default=10.0, ge=0, le=100, allow_inf_nan=False)
    y: float = Field(default=10.0, ge=0, le=100, allow_inf_nan=False)
    width: float = Field(default=20.0, gt=0, le=100, allow_inf_nan=False)
    height: float = Field(default=10.0, gt=0, le=100, allow_inf_nan=False)
    blur_strength: int = Field(default=20, ge=1, le=100)
    replacement_text: str = Field(default="", max_length=200)
    logo_path: str = ""
    logo_url: str = ""
    font_size: int = Field(default=24, ge=8, le=200)
    text_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    bg_color: str = Field(default="#000000", pattern=r"^#[0-9A-Fa-f]{6}$")
    bg_opacity: float = Field(default=0.6, ge=0, le=1)

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
    cleanup_regions: List[CleanupRegion] = Field(default_factory=list)
    cleaned_video_url: str = ""
    cleaned_video_path: str = ""
    status: str = "uploaded"  # "uploaded", "analyzing", "generating", "ready", "cleaning", "exporting", "completed"
    progress: int = 0
    status_message: str = "Ready"

class GenerateReelsRequest(BaseModel):
    clip_duration: float = Field(default=30.0, ge=5, le=120)
    target_count: int = Field(default=10, ge=1, le=30)
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    mode: Literal["smart_crop", "blur_bg", "fit"] = "smart_crop"
    auto_captions: bool = True
    caption_language: Literal["en", "hi", "hinglish"] = "en"
    caption_style: Literal["bold_outline", "clean_pill", "karaoke", "classic"] = "bold_outline"

class ExportRequest(BaseModel):
    clip_ids: List[str] = Field(min_length=1, max_length=30)
    quality: str = "high"
    fps: int = 30
    resolution: str = "1080x1920"

class CleanupRequest(BaseModel):
    regions: List[CleanupRegion] = Field(min_length=1, max_length=20)
    authorization_confirmed: bool = False
    export_name: Optional[str] = None

class CleanupRegionsRequest(BaseModel):
    regions: List[CleanupRegion] = Field(max_length=20)

class RenameProjectRequest(BaseModel):
    name: str
