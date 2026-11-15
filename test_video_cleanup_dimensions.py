import json
import subprocess
import sys
import unittest
import uuid
from fractions import Fraction
from pathlib import Path

from PIL import Image

backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from config import EXPORTS_DIR, FFPROBE_BIN, TEMP_DIR, THUMBNAILS_DIR
from models import CleanupRegion
from services.video_analyzer import probe_video
from services.video_cleanup import (
    LAMA_MODEL,
    LAMA_PYTHON,
    LAMA_SCRIPT,
    render_cleanup_preview_frame,
    render_cleanup_video,
)


def _media_properties(path: Path) -> dict:
    result = subprocess.run(
        [
            FFPROBE_BIN,
            "-v", "error",
            "-show_streams",
            "-show_format",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    video = next(stream for stream in data["streams"] if stream.get("codec_type") == "video")
    return {
        "width": video["width"],
        "height": video["height"],
        "sar": video.get("sample_aspect_ratio"),
        "dar": video.get("display_aspect_ratio"),
        "fps": Fraction(video["avg_frame_rate"]),
        "duration": float(data["format"]["duration"]),
        "has_audio": any(
            stream.get("codec_type") == "audio" for stream in data["streams"]
        ),
    }


class VideoCleanupDimensionTests(unittest.TestCase):
    def test_inpaint_preserves_anamorphic_4_3_dimensions_aspect_and_audio(self):
        if not all(path.is_file() for path in (LAMA_PYTHON, LAMA_SCRIPT, LAMA_MODEL)):
            self.skipTest("The configured local LaMa environment is unavailable.")

        project_id = f"cleanup_aspect_{uuid.uuid4().hex[:12]}"
        blur_project_id = f"{project_id}_blur"
        source = TEMP_DIR / f"{project_id}.mp4"
        output = EXPORTS_DIR / f"{project_id}_cleaned.mp4"
        blur_output = EXPORTS_DIR / f"{blur_project_id}_cleaned.mp4"
        preview = THUMBNAILS_DIR / f"{project_id}_cleanup_preview.jpg"

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=2:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-vf", "setsar=3/4",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest",
                    str(source),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            source_properties = _media_properties(source)
            self.assertEqual((source_properties["width"], source_properties["height"]), (320, 180))
            self.assertEqual(source_properties["sar"], "3:4")
            self.assertEqual(
                Fraction(source_properties["dar"].replace(":", "/")),
                Fraction(4, 3),
            )

            metadata = probe_video(source)
            regions = [
                CleanupRegion(id="watermark", type="inpaint", x=40, y=40, width=20, height=20)
            ]
            cleaned = render_cleanup_video(source, regions, project_id, metadata)
            output_properties = _media_properties(cleaned)

            self.assertEqual(
                (output_properties["width"], output_properties["height"]),
                (source_properties["width"], source_properties["height"]),
            )
            self.assertEqual(output_properties["sar"], source_properties["sar"])
            self.assertEqual(output_properties["dar"], source_properties["dar"])
            self.assertEqual(output_properties["fps"], source_properties["fps"])
            self.assertAlmostEqual(
                output_properties["duration"], source_properties["duration"], delta=0.05
            )
            self.assertEqual(output_properties["has_audio"], source_properties["has_audio"])

            blurred = render_cleanup_video(
                source,
                [
                    CleanupRegion(
                        id="blur",
                        type="blur",
                        x=40,
                        y=40,
                        width=20,
                        height=20,
                        blur_strength=5,
                    )
                ],
                blur_project_id,
                metadata,
            )
            blur_properties = _media_properties(blurred)
            self.assertEqual(
                (blur_properties["width"], blur_properties["height"]),
                (source_properties["width"], source_properties["height"]),
            )
            self.assertEqual(blur_properties["sar"], source_properties["sar"])
            self.assertEqual(blur_properties["dar"], source_properties["dar"])
            self.assertEqual(blur_properties["fps"], source_properties["fps"])
            self.assertEqual(blur_properties["has_audio"], source_properties["has_audio"])

            render_cleanup_preview_frame(
                source, regions, 1.0, project_id, metadata
            )
            with Image.open(preview) as preview_frame:
                self.assertEqual(preview_frame.size, (320, 180))
        finally:
            for path in (source, output, blur_output, preview):
                path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
