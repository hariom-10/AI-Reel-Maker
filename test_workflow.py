import asyncio
import io
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from config import EXPORTS_DIR, FFPROBE_BIN, TEMP_DIR, THUMBNAILS_DIR, TRANSCRIPTS_DIR, UPLOADS_DIR
from models import (
    BlurRegion,
    CaptionConfig,
    CleanupRegion,
    CleanupRegionsRequest,
    CleanupRequest,
    ClipConfig,
    CropConfig,
    GenerateReelsRequest,
    Project,
    SubtitleItem,
)
from services.project_store import project_store
from services import transcriber
from services.transcriber import whisper_available
from services.video_analyzer import analyze_video_scenes, probe_video
from services.reel_generator import generate_automatic_reels
from services.video_cleanup import (
    build_cleanup_filters,
    render_cleanup_preview_frame,
    render_cleanup_video,
)
from services.video_editor import create_export_zip, render_clip
from services.ffmpeg_runner import run_ffmpeg


def run_test():
    project_id = f"workflow_{uuid.uuid4().hex[:12]}"
    test_video = TEMP_DIR / f"{project_id}.mp4"
    silent_video = TEMP_DIR / f"{project_id}_silent.mp4"
    rendered_path = None
    silent_rendered_path = None
    zip_path = None
    cleaned_path = None
    preview_path = None
    transcript_cache = None
    print("=== Testing AI Reel Maker Video Workflow ===")

    try:
        print("1. Generating test footage...")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=0x111827:s=1280x720:d=10",
                "-f", "lavfi", "-i", "color=c=0x4338ca:s=1280x720:d=10",
                "-f", "lavfi", "-i", "sine=f=500:d=20",
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map", "[v]", "-map", "2:a", "-c:v", "libx264",
                "-c:a", "aac", "-pix_fmt", "yuv420p", str(test_video),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print("2. Probing video metadata...")
        metadata = probe_video(test_video)
        assert metadata.duration > 0
        assert metadata.width == 1280 and metadata.height == 720

        from fastapi import BackgroundTasks, HTTPException, UploadFile
        from app import (
            preview_cleanup_frame,
            generate_reels,
            run_background_generation,
            save_cleanup_regions,
            trigger_video_cleanup,
            upload_video,
        )

        test_project = Project(
            id=project_id,
            name="Workflow security test",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            video_filename=test_video.name,
            video_path=str(test_video),
            video_url=f"/media/uploads/{test_video.name}",
            metadata=metadata,
            status="ready",
        )
        project_store.save_project(test_project)
        saved_regions = save_cleanup_regions(
            project_id,
            CleanupRegionsRequest(
                regions=[CleanupRegion(id="saved_region", x=1, y=2, width=3, height=4)]
            ),
        )
        assert saved_regions["regions"][0].id == "saved_region"
        assert project_store.get_project(project_id).cleanup_regions[0].id == "saved_region"
        cleanup_request = CleanupRequest(
            regions=[CleanupRegion(id="test", x=10, y=10, width=20, height=20)],
            authorization_confirmed=False,
        )
        try:
            trigger_video_cleanup(project_id, cleanup_request, BackgroundTasks())
            raise AssertionError("Cleanup must reject missing authorization.")
        except HTTPException as exc:
            assert exc.status_code == 403
        try:
            preview_cleanup_frame(project_id, cleanup_request, timestamp=0)
            raise AssertionError("Cleanup preview must reject missing authorization.")
        except HTTPException as exc:
            assert exc.status_code == 403
        assert project_store.get_project("../outside") is None
        existing_uploads = set(UPLOADS_DIR.iterdir())
        try:
            asyncio.run(
                upload_video(
                    file=UploadFile(
                        file=io.BytesIO(b"not a video"),
                        filename="..\\escape.mp4",
                    ),
                    name=None,
                )
            )
            raise AssertionError("Upload must reject files without a valid video stream.")
        except HTTPException as exc:
            assert exc.status_code == 400
        assert set(UPLOADS_DIR.iterdir()) == existing_uploads

        print("3. Analyzing scenes...")
        scenes = analyze_video_scenes(test_video, project_id)
        assert len(scenes) >= 1
        assert all(0.0 <= scene.score <= 1.0 for scene in scenes)
        assert all(0.0 <= scene.visual_activity <= 1.0 for scene in scenes)
        test_project = project_store.get_project(project_id)
        test_project.scenes = scenes
        project_store.save_project(test_project)

        print("4. Generating reel candidates in the background...")
        request = GenerateReelsRequest(
            target_count=2,
            clip_duration=10.0,
            aspect_ratio="9:16",
            mode="blur_bg",
            auto_captions=True,
        )
        response = generate_reels(project_id, request, BackgroundTasks())
        assert response["project"].status == "generating"
        run_background_generation(project_id, request)
        generated_project = project_store.get_project(project_id)
        assert generated_project.status == "ready", generated_project.status_message
        reels = generated_project.clips
        assert len(reels) >= 1
        if not whisper_available():
            assert all(not reel.subtitles for reel in reels)
            assert "Captions were skipped" in generated_project.status_message
        assert all(reel.crop_config.aspect_ratio == "9:16" for reel in reels)
        assert len({(reel.start_time, reel.end_time) for reel in reels}) == len(reels)
        assert all(
            0 <= reel.start_time < reel.end_time <= metadata.duration
            and abs(reel.duration - (reel.end_time - reel.start_time)) <= 0.02
            for reel in reels
        )
        for index, reel in enumerate(reels):
            for other in reels[index + 1:]:
                overlap = max(
                    0.0,
                    min(reel.end_time, other.end_time) - max(reel.start_time, other.start_time),
                )
                assert overlap == 0.0
        reels[0].crop_config.blur_region = BlurRegion(x=10, y=10, width=20, height=20)

        no_caption_clips = generate_automatic_reels(
            scenes=scenes,
            video_duration=metadata.duration,
            video_path=test_video,
            project_id=project_id,
            target_count=1,
            target_duration=10,
            auto_captions=False,
            transcript=[],
        )
        assert no_caption_clips
        assert not no_caption_clips[0].caption_config.enabled
        assert not no_caption_clips[0].subtitles

        print("4a. Testing chunked transcription offsets and cache reuse...")
        transcript_cache = TRANSCRIPTS_DIR / f"{project_id}_offsets.json"

        def fake_extract(command, duration, progress_callback=None, loglevel="error"):
            Path(command[-1]).write_bytes(b"mock audio data larger than the wave header minimum")
            return ""

        def fake_chunk_transcription(audio_path, language, clip_start_time):
            return [
                SubtitleItem(
                    id="chunk_sub",
                    start_time=clip_start_time + 2.0,
                    end_time=clip_start_time + 3.0,
                    text="sample speech",
                )
            ]

        with (
            patch.object(transcriber, "whisper_available", return_value=True),
            patch.object(transcriber, "_video_has_audio", return_value=True),
            patch.object(transcriber, "run_ffmpeg", side_effect=fake_extract),
            patch.object(transcriber, "transcribe_audio_whisper", side_effect=fake_chunk_transcription),
        ):
            full_transcript = transcriber.transcribe_video(
                test_video,
                f"{project_id}_offsets",
                65.0,
            )
        assert full_transcript is not None
        assert [item.start_time for item in full_transcript] == [2.0, 31.0, 61.0]
        assert len(transcriber.load_cached_transcript(
            test_video,
            f"{project_id}_offsets",
            65.0,
        ) or []) == 3

        print("5. Rendering a reel...")
        render_progress = []
        rendered = render_clip(
            test_video,
            reels[0],
            project_id,
            progress_callback=lambda percent, _message: render_progress.append(percent),
        )
        assert rendered.status == "exported", rendered.error_message
        rendered_path = Path(rendered.output_path)
        assert rendered_path.exists()
        assert any(percent > 0 for percent in render_progress)
        rendered_metadata = probe_video(rendered_path)
        assert (rendered_metadata.width, rendered_metadata.height) == (1080, 1920)
        assert rendered_metadata.fps == 30
        audio_probe = subprocess.run(
            [
                FFPROBE_BIN,
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(rendered_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        assert "audio" in audio_probe.stdout.splitlines()

        print("5a. Testing export when the source has no audio stream...")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=320x180:d=5",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(silent_video),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        silent_clip = render_clip(
            silent_video,
            ClipConfig(
                clip_id="silent_audio_check",
                title="Silent source check",
                start_time=0,
                end_time=5,
                duration=5,
                crop_config=CropConfig(aspect_ratio="9:16", mode="fit"),
                caption_config=CaptionConfig(enabled=False),
            ),
            project_id,
        )
        assert silent_clip.status == "exported", silent_clip.error_message
        silent_rendered_path = Path(silent_clip.output_path)
        silent_audio_probe = subprocess.run(
            [
                FFPROBE_BIN,
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(silent_rendered_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        assert not silent_audio_probe.stdout.strip()

        print("6. Testing FFmpeg job cancellation...")

        def cancel_render(_percent, _message):
            raise InterruptedError("Cancelled by test.")

        try:
            run_ffmpeg(
                [
                    "ffmpeg", "-re", "-f", "lavfi", "-i",
                    "color=c=black:s=64x64:d=5", "-f", "null", "-",
                ],
                5,
                cancel_render,
            )
            raise AssertionError("FFmpeg runner must propagate cancellation.")
        except InterruptedError:
            pass

        print("6. Testing authorized region cleanup...")
        cleanup_regions = [
            CleanupRegion(
                id="authorized_region",
                type="inpaint",
                x=75,
                y=8,
                width=18,
                height=10,
            ),
            CleanupRegion(
                id="custom_text",
                type="add_text",
                x=5,
                y=5,
                width=20,
                height=10,
                replacement_text="Authorized: text, % [ok]",
            ),
        ]
        filters = build_cleanup_filters(cleanup_regions, metadata.width, metadata.height)
        assert "[cleanup_out]" in filters and "delogo=" in filters and r"\," in filters
        original_size = test_video.stat().st_size
        cleaned_path = render_cleanup_video(
            test_video,
            cleanup_regions,
            project_id,
            metadata,
        )
        assert cleaned_path and cleaned_path.exists()
        assert test_video.stat().st_size == original_size
        preview_url = render_cleanup_preview_frame(
            test_video,
            cleanup_regions,
            2,
            project_id,
            metadata,
        )
        assert preview_url
        preview_path = THUMBNAILS_DIR / Path(preview_url).name
        assert preview_path.exists()

        print("7. Creating a ZIP bundle...")
        zip_url = create_export_zip(project_id, [rendered])
        assert zip_url
        zip_path = EXPORTS_DIR / Path(zip_url).name
        assert zip_path.exists()

        print("All workflow checks passed.")
    finally:
        for path in (
            test_video,
            silent_video,
            rendered_path,
            silent_rendered_path,
            zip_path,
            cleaned_path,
            preview_path,
            transcript_cache,
        ):
            if path and path.exists():
                path.unlink()
        for path in THUMBNAILS_DIR.glob(f"{project_id}_*.jpg"):
            path.unlink()
        project_file = project_store._get_path(project_id)
        if project_file.exists():
            project_file.unlink()


if __name__ == "__main__":
    run_test()
