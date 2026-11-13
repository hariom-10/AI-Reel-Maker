import argparse
import sys
from pathlib import Path
from datetime import datetime
import subprocess

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from config import UPLOADS_DIR, THUMBNAILS_DIR
from services.video_analyzer import probe_video, analyze_video_scenes, extract_thumbnail
from services.reel_generator import generate_automatic_reels
from services.project_store import project_store
from models import Project

def create_demo():
    parser = argparse.ArgumentParser(description="Create a synthetic local demo project.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the existing demo video/project if present.",
    )
    args = parser.parse_args()

    print("Generating Starter Demo Video...")
    video_path = UPLOADS_DIR / "starter_demo_video.mp4"
    project_id = "demo_starter_project"
    project_path = project_store._get_path(project_id)
    if not args.overwrite and (video_path.exists() or project_path.exists()):
        raise FileExistsError(
            "The starter demo already exists. Pass --overwrite to replace it."
        )

    # FFmpeg command to create a multi-scene demo video
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=10:size=1280x720:rate=30",
        "-f", "lavfi", "-i", "smptebars=duration=10:size=1280x720:rate=30",
        "-f", "lavfi", "-i", "testsrc2=duration=10:size=1280x720:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map", "[v]", "-map", "3:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(video_path)
    ]
    subprocess.run(cmd, check=True)

    print("Probing metadata...")
    metadata = probe_video(video_path)

    cover_thumb = THUMBNAILS_DIR / f"{project_id}_cover.jpg"
    extract_thumbnail(video_path, 2.0, cover_thumb)

    print("Analyzing scenes...")
    scenes = analyze_video_scenes(video_path, project_id)

    print("Generating reels...")
    clips = generate_automatic_reels(
        scenes=scenes,
        video_duration=metadata.duration,
        video_path=video_path,
        project_id=project_id,
        target_count=3,
        target_duration=10.0,
        aspect_ratio="9:16",
        mode="smart_crop",
        auto_captions=True,
        caption_language="en",
        caption_style="bold_outline"
    )

    proj = Project(
        id=project_id,
        name="AI Reel Maker Demo Showcase",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        video_filename="starter_demo_video.mp4",
        video_path=str(video_path),
        video_url="/media/uploads/starter_demo_video.mp4",
        metadata=metadata,
        scenes=scenes,
        clips=clips,
        status="ready",
        progress=100,
        status_message="Ready for preview and export"
    )

    project_store.save_project(proj)
    print("Demo project successfully created!")

if __name__ == "__main__":
    create_demo()
