import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
PROJECTS_DIR = DATA_DIR / "projects"
EXPORTS_DIR = DATA_DIR / "exports"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
TEMP_DIR = DATA_DIR / "temp"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"

# Ensure all critical storage directories exist
for directory in [
    DATA_DIR,
    UPLOADS_DIR,
    PROJECTS_DIR,
    EXPORTS_DIR,
    THUMBNAILS_DIR,
    TEMP_DIR,
    TRANSCRIPTS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".ts", ".m4v"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 * 1024  # 50 GB local limit

FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"
