"""Central configuration for Forensic-Search."""
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

# Folders
MEDIA_DIR = ROOT / "media"          # drop your audio/video files here
DATA_DIR = ROOT / "data"            # generated captions + index live here
CAPTIONS_DIR = DATA_DIR / "captions"
INDEX_FILE = DATA_DIR / "index.json"

# Whisper
WHISPER_MODEL = "base"              # tiny | base | small | medium | large
WHISPER_LANGUAGE = None             # None = auto-detect, or e.g. "en"

# Sound-event detection
ENABLE_SOUND_EVENTS = True
SOUND_EVENT_WINDOW_SEC = 1.0        # YAMNet hop window
SOUND_EVENT_MIN_SCORE = 0.35        # confidence cutoff
SOUND_EVENT_MIN_DURATION = 1.5      # merge adjacent detections shorter than this

# Supported media extensions
MEDIA_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg",
              ".mp4", ".mkv", ".mov", ".avi", ".webm"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}

# Visual analysis (object detection + scene captioning on sampled frames)
ENABLE_VISUAL_OBJECTS = True
VISUAL_SAMPLE_SEC = 2.0             # one frame every N seconds
VISUAL_YOLO_MODEL = "yolov8n.pt"    # nano = fastest; auto-downloads on first use
VISUAL_YOLO_CONF = 0.35
VISUAL_BLIP_MODEL = "Salesforce/blip-image-captioning-base"

# NLP query expansion (lemma + WordNet synonyms)
ENABLE_NLP_EXPANSION = True

# Web UI
import os
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8080))

for d in (MEDIA_DIR, DATA_DIR, CAPTIONS_DIR):
    d.mkdir(parents=True, exist_ok=True)
