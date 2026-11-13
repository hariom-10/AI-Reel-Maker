export interface VideoMetadata {
  duration: number;
  width: number;
  height: number;
  fps: number;
  bitrate: number;
  codec: string;
  format_name: string;
  size_bytes: number;
}

export interface DetectedScene {
  scene_id: string;
  start_time: number;
  end_time: number;
  duration: number;
  thumbnail_url: string;
  score: number;
  audio_activity: number;
  visual_activity: number;
  dialogue_density: number;
  summary: string;
  selected: boolean;
}

export interface SubtitleItem {
  id: string;
  start_time: number;
  end_time: number;
  text: string;
}

export interface CaptionConfig {
  enabled: boolean;
  language: string; // "en" | "hi" | "hinglish"
  font_family: string;
  font_size: number;
  text_color: string;
  bg_color: string;
  bg_opacity: number;
  position: string; // "bottom" | "center" | "top" | "custom"
  y_percent: number;
  style: string; // "bold_outline" | "clean_pill" | "karaoke" | "classic"
}

export interface BlurRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CropConfig {
  aspect_ratio: "9:16" | "16:9" | "1:1";
  mode: "smart_crop" | "blur_bg" | "fit";
  center_x_percent: number;
  blur_strength: number;
  blur_region?: BlurRegion;
}

export interface ClipConfig {
  clip_id: string;
  title: string;
  start_time: number;
  end_time: number;
  duration: number;
  score: number;
  thumbnail_url: string;
  crop_config: CropConfig;
  caption_config: CaptionConfig;
  subtitles: SubtitleItem[];
  status: "ready" | "rendering" | "exported" | "error";
  output_url: string;
  output_path: string;
  error_message: string;
}

export interface CleanupRegion {
  id: string;
  type: "inpaint" | "blur" | "replace_logo" | "add_text";
  x: number;      // 0-100 percentage
  y: number;
  width: number;
  height: number;
  blur_strength: number;
  replacement_text?: string;
  logo_url?: string;
  font_size?: number;
  text_color?: string;
  bg_color?: string;
  bg_opacity?: number;
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  video_filename: string;
  video_path: string;
  video_url: string;
  metadata: VideoMetadata;
  scenes: DetectedScene[];
  clips: ClipConfig[];
  cleanup_regions?: CleanupRegion[];
  cleaned_video_url?: string;
  cleaned_video_path?: string;
  status: "uploaded" | "analyzing" | "generating" | "ready" | "cleaning" | "exporting" | "completed";
  progress: number;
  status_message: string;
}

export interface DashboardStats {
  total_videos: number;
  total_clips: number;
  processing_videos: number;
  completed_projects: number;
  recent_projects: Project[];
}

export interface GenerateReelsParams {
  clip_duration: number;
  target_count: number;
  aspect_ratio: "9:16" | "16:9" | "1:1";
  mode: "smart_crop" | "blur_bg" | "fit";
  auto_captions: boolean;
  caption_language: string;
  caption_style: string;
}

export interface CleanupParams {
  regions: CleanupRegion[];
  authorization_confirmed: boolean;
  export_name?: string;
}
