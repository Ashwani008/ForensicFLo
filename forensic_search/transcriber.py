"""Speech-to-text using OpenAI Whisper (local)."""
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any

import whisper

_model_cache: Dict[str, Any] = {}


def _get_model(name: str):
    if name not in _model_cache:
        _model_cache[name] = whisper.load_model(name)
    return _model_cache[name]


def transcribe(audio_path: Path, model_name: str = "base",
               language: str | None = None) -> List[Dict[str, Any]]:
    """Return a list of speech segments: {start, end, text, kind='speech'}."""
    model = _get_model(model_name)
    result = model.transcribe(str(audio_path), language=language, verbose=False)
    segments = []
    for seg in result.get("segments", []):
        text = seg["text"].strip()
        if not text:
            continue
        segments.append({
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "text": text,
            "kind": "speech",
        })
    return segments
