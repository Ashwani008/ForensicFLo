"""Non-speech audio event detection using YAMNet (AudioSet, 521 classes).

Produces caption-style segments like '[train horn]', '[dog barking]', etc.
Gracefully no-ops if TensorFlow is not available.
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import csv
import io
import urllib.request

import numpy as np
import soundfile as sf

_yamnet = None
_class_names: List[str] | None = None

# Classes we always treat as "speech" and therefore skip (Whisper handles them)
_SPEECH_CLASSES = {
    "Speech", "Male speech, man speaking", "Female speech, woman speaking",
    "Child speech, kid speaking", "Conversation", "Narration, monologue",
    "Babbling", "Whispering",
}
# Generic background classes that add little signal — filter out
_NOISE_CLASSES = {"Silence", "Inside, small room", "Inside, large room or hall",
                  "Inside, public space", "Outside, urban or manmade",
                  "Outside, rural or natural", "White noise", "Pink noise",
                  "Background noise", "Sound effect", "Music"}


def _load_model():
    global _yamnet, _class_names
    if _yamnet is not None:
        return _yamnet, _class_names
    import tensorflow_hub as hub  # lazy import
    _yamnet = hub.load("https://tfhub.dev/google/yamnet/1")
    # Read class map
    class_map_path = _yamnet.class_map_path().numpy().decode("utf-8")
    with open(class_map_path) as f:
        reader = csv.DictReader(f)
        _class_names = [row["display_name"] for row in reader]
    return _yamnet, _class_names


def _merge(events: List[Dict[str, Any]], min_gap: float = 0.5) -> List[Dict[str, Any]]:
    """Merge adjacent same-label events."""
    if not events:
        return events
    events.sort(key=lambda e: (e["text"], e["start"]))
    merged: List[Dict[str, Any]] = []
    for e in events:
        if merged and merged[-1]["text"] == e["text"] and e["start"] - merged[-1]["end"] <= min_gap:
            merged[-1]["end"] = max(merged[-1]["end"], e["end"])
        else:
            merged.append(dict(e))
    merged.sort(key=lambda e: e["start"])
    return merged


def detect_events(audio_path: Path, min_score: float = 0.35,
                  min_duration: float = 1.5) -> List[Dict[str, Any]]:
    """Return non-speech sound-event segments: {start, end, text, kind='sound'}."""
    try:
        model, class_names = _load_model()
    except Exception as ex:
        print(f"[sound_events] YAMNet unavailable, skipping: {ex}")
        return []

    waveform, sr = sf.read(str(audio_path), dtype="float32")
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)
    if sr != 16000:
        import librosa
        waveform = librosa.resample(waveform, orig_sr=sr, target_sr=16000)
        sr = 16000

    scores, _, _ = model(waveform)
    scores = scores.numpy()  # shape (frames, 521); each frame = 0.48s, hop 0.48s
    hop = 0.48

    raw: List[Dict[str, Any]] = []
    for i, frame in enumerate(scores):
        top_idx = int(np.argmax(frame))
        top_score = float(frame[top_idx])
        label = class_names[top_idx]
        if top_score < min_score:
            continue
        if label in _SPEECH_CLASSES or label in _NOISE_CLASSES:
            continue
        start = i * hop
        end = start + hop
        raw.append({"start": start, "end": end, "text": f"[{label.lower()}]",
                    "kind": "sound", "score": top_score})

    merged = _merge(raw, min_gap=0.6)
    merged = [m for m in merged if (m["end"] - m["start"]) >= min_duration or m.get("score", 0) >= 0.6]
    return merged
