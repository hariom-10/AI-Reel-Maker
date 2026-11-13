import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from services.video_analyzer import probe_video, analyze_video_scenes
from services.reel_generator import generate_automatic_reels
from services.video_editor import render_clip, create_export_zip
from services.project_store import project_store
from models import Project, CropConfig, CaptionConfig, SubtitleItem

def run_test():
    print("=== Testing AI Reel Maker Video Workflow ===")
    
    # 1. Generate test footage using ffmpeg
    test_video = Path("workflow_test.mp4")
    print(f"1. Generating test footage {test_video}...")
    cmd = (
        'ffmpeg -y -f lavfi -i "color=c=0x111827:s=1280x720:d=10" '
        '-f lavfi -i "color=c=0x4338ca:s=1280x720:d=10" '
        '-f lavfi -i "sine=f=500:d=20" '
        '-filter_complex "[0:v][1:v]concat=n=2:v=1:a=0[v]" '
        '-map "[v]" -map 2:a -c:v libx264 -c:a aac -pix_fmt yuv420p workflow_test.mp4'
    )
    res = os.system(cmd)
    assert res == 0, "FFmpeg failed to create test video"

    # 2. Probe video metadata
    print("2. Probing video metadata...")
    meta = probe_video(test_video)
    print(f"   Resolution: {meta.width}x{meta.height}, Duration: {meta.duration}s, FPS: {meta.fps}")
    assert meta.duration > 0

    # 3. Detect scenes
    print("3. Analyzing video scenes with AI heuristics...")
    scenes = analyze_video_scenes(test_video, "proj_test")
    print(f"   Detected {len(scenes)} scenes.")
    assert len(scenes) >= 1

    # 4. Generate automatic reels
    print("4. Generating automatic 9:16 reels...")
    reels = generate_automatic_reels(
        scenes=scenes,
        video_duration=meta.duration,
        video_path=test_video,
        project_id="proj_test",
        target_count=2,
        target_duration=10.0,
        aspect_ratio="9:16",
        mode="blur_bg",
        auto_captions=True,
        caption_language="en",
        caption_style="bold_outline"
    )
    print(f"   Generated {len(reels)} reel candidates.")
    assert len(reels) >= 1

    # 5. Render first reel
    print("5. Rendering vertical 9:16 reel with styled subtitles...")
    first_reel = reels[0]
    rendered = render_clip(test_video, first_reel, "proj_test")
    print(f"   Render status: {rendered.status}")
    print(f"   Output path: {rendered.output_path}")
    assert rendered.status == "exported"
    assert Path(rendered.output_path).exists()

    # 6. Create ZIP bundle
    print("6. Creating batch export ZIP package...")
    zip_url = create_export_zip("proj_test", [rendered])
    print(f"   ZIP Package ready: {zip_url}")
    assert zip_url is not None

    # Cleanup
    if test_video.exists():
        test_video.unlink()
    if Path(rendered.output_path).exists():
        Path(rendered.output_path).unlink()

    print("\n✅ All workflow tests passed successfully!")

if __name__ == "__main__":
    run_test()
