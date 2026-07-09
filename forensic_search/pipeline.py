"""Top-level orchestration: process a single media file end-to-end."""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any

from . import audio_utils, transcriber, sound_events, caption_generator

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}


def process_file(media_path: Path, captions_dir: Path,
                 whisper_model: str = "base",
                 language: str | None = None,
                 enable_sound_events: bool = True,
                 min_score: float = 0.35,
                 min_duration: float = 1.5,
                 enable_visual: bool = False,
                 visual_sample_sec: float = 2.0,
                 visual_yolo_model: str = "yolov8n.pt",
                 visual_yolo_conf: float = 0.35,
                 visual_blip_model: str = "Salesforce/blip-image-captioning-base"
                 ) -> Dict[str, Any]:
    """Transcribe + detect sound events + (optionally) describe on-screen visuals,
    then write SRT/VTT/JSON. Returns metadata."""
    print(f"[process] {media_path.name}: extracting audio...")
    wav = audio_utils.extract_audio(media_path)
    try:
        print(f"[process] {media_path.name}: transcribing speech ({whisper_model})...")
        speech = transcriber.transcribe(wav, model_name=whisper_model, language=language)

        events = []
        if enable_sound_events:
            print(f"[process] {media_path.name}: detecting sound events...")
            events = sound_events.detect_events(wav, min_score=min_score,
                                                min_duration=min_duration)

        visuals = []
        if enable_visual and media_path.suffix.lower() in VIDEO_EXTS:
            try:
                from . import visual  # lazy: avoids importing torch unless needed
                visuals = visual.analyze_video(
                    media_path,
                    every_sec=visual_sample_sec,
                    yolo_model=visual_yolo_model,
                    yolo_conf=visual_yolo_conf,
                    blip_model=visual_blip_model,
                )
            except Exception as ex:
                print(f"[process] {media_path.name}: visual analysis failed: {ex}")

        all_segments = speech + events + visuals
        paths = caption_generator.write_captions(media_path.name, all_segments, captions_dir)
        print(f"[process] {media_path.name}: {len(speech)} speech + {len(events)} sound"
              f" + {len(visuals)} visual segments")
        return {
            "media": media_path.name,
            "segment_count": len(all_segments),
            "speech_count": len(speech),
            "sound_count": len(events),
            "visual_count": len(visuals),
            "paths": {k: str(v) for k, v in paths.items()},
            "segments": sorted(all_segments, key=lambda s: s["start"]),
        }
    finally:
        try:
            wav.unlink(missing_ok=True)
        except Exception:
            pass
