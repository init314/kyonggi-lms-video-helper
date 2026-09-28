from pathlib import Path
import sys


DEFAULT_CHUNK_SIZE = 8000
DEFAULT_LANGUAGE = "ko"
DEFAULT_OVERLAP = 500
APP_ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = APP_ROOT / "output"
DEFAULT_DOWNLOAD_DIR = APP_ROOT / "downloads"
DEFAULT_MODEL_REF = "large-v3-turbo"
SUPPORTED_AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".flac")
SUPPORTED_VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".mpeg", ".mpg", ".m4v")
SUPPORTED_MEDIA_EXTENSIONS = SUPPORTED_AUDIO_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS
