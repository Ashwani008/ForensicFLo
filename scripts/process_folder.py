"""CLI: batch-process every media file in a folder.

Usage:
    python -m scripts.process_folder                # uses config.MEDIA_DIR
    python -m scripts.process_folder /path/to/media
    python -m scripts.process_folder --model small --no-events
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/process_folder.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from forensic_search import pipeline, indexer
from forensic_search.audio_utils import get_ffmpeg


def main():
    ap = argparse.ArgumentParser(description="Generate captions + keyword index for a media folder.")
    ap.add_argument("folder", nargs="?", default=str(config.MEDIA_DIR),
                    help="Folder containing audio/video files (default: ./media)")
    ap.add_argument("--model", default=config.WHISPER_MODEL,
                    help="Whisper model: tiny|base|small|medium|large")
    ap.add_argument("--language", default=config.WHISPER_LANGUAGE,
                    help="Force language code (e.g. 'en'); default auto-detect")
    ap.add_argument("--no-events", action="store_true",
                    help="Disable non-speech sound-event detection")
    ap.add_argument("--no-visual", action="store_true",
                    help="Disable visual object detection / scene captioning")
    ap.add_argument("--force", action="store_true",
                    help="Re-process files even if captions already exist")
    args = ap.parse_args()

    folder = Path(args.folder).resolve()
    if not folder.is_dir():
        print(f"ERROR: not a directory: {folder}")
        sys.exit(1)

    get_ffmpeg()  # fail fast with a clear error if ffmpeg is missing

    files = [p for p in sorted(folder.iterdir())
             if p.is_file() and p.suffix.lower() in config.MEDIA_EXTS]
    if not files:
        print(f"No supported media files in {folder}")
        sys.exit(0)

    print(f"Found {len(files)} media file(s) in {folder}")
    for f in files:
        out_json = config.CAPTIONS_DIR / f"{f.stem}.json"
        if out_json.exists() and not args.force:
            print(f"[skip] {f.name} (already processed; use --force to redo)")
            continue
        try:
            pipeline.process_file(
                f, config.CAPTIONS_DIR,
                whisper_model=args.model,
                language=args.language,
                enable_sound_events=(not args.no_events and config.ENABLE_SOUND_EVENTS),
                min_score=config.SOUND_EVENT_MIN_SCORE,
                min_duration=config.SOUND_EVENT_MIN_DURATION,
                enable_visual=(not args.no_visual
                               and getattr(config, "ENABLE_VISUAL_OBJECTS", False)),
                visual_sample_sec=getattr(config, "VISUAL_SAMPLE_SEC", 2.0),
                visual_yolo_model=getattr(config, "VISUAL_YOLO_MODEL", "yolov8n.pt"),
                visual_yolo_conf=getattr(config, "VISUAL_YOLO_CONF", 0.35),
                visual_blip_model=getattr(config, "VISUAL_BLIP_MODEL",
                                          "Salesforce/blip-image-captioning-base"),
            )
        except Exception as ex:
            print(f"[error] {f.name}: {ex}")

    indexer.build_index(config.CAPTIONS_DIR, config.INDEX_FILE)
    print("Done. Run `python app.py` to open the search UI.")


if __name__ == "__main__":
    main()
