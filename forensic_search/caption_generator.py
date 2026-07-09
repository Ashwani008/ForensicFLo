"""Generate SRT + a structured JSON caption file from speech + sound events."""
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _for_overlay(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Visual descriptions stay in JSON (searchable) but are kept out of the
    # SRT/VTT track so they don't clutter the on-screen caption overlay.
    return [s for s in segments if s.get("kind") != "visual"]


def to_srt(segments: List[Dict[str, Any]]) -> str:
    segments = sorted(_for_overlay(segments), key=lambda s: s["start"])
    out = []
    for i, seg in enumerate(segments, 1):
        out.append(str(i))
        out.append(f"{_ts(seg['start'])} --> {_ts(seg['end'])}")
        out.append(seg["text"])
        out.append("")
    return "\n".join(out)


def to_vtt(segments: List[Dict[str, Any]]) -> str:
    """WebVTT for the browser <track> element."""
    segments = sorted(_for_overlay(segments), key=lambda s: s["start"])
    out = ["WEBVTT", ""]
    for seg in segments:
        start = _ts(seg["start"]).replace(",", ".")
        end = _ts(seg["end"]).replace(",", ".")
        out.append(f"{start} --> {end}")
        out.append(seg["text"])
        out.append("")
    return "\n".join(out)


def write_captions(media_name: str, segments: List[Dict[str, Any]],
                   captions_dir: Path) -> Dict[str, Path]:
    """Write .srt, .vtt, .json next to each other; return their paths."""
    stem = Path(media_name).stem
    srt_path = captions_dir / f"{stem}.srt"
    vtt_path = captions_dir / f"{stem}.vtt"
    json_path = captions_dir / f"{stem}.json"

    srt_path.write_text(to_srt(segments), encoding="utf-8")
    vtt_path.write_text(to_vtt(segments), encoding="utf-8")
    json_path.write_text(json.dumps({
        "media": media_name,
        "segments": sorted(segments, key=lambda s: s["start"]),
    }, indent=2), encoding="utf-8")
    return {"srt": srt_path, "vtt": vtt_path, "json": json_path}
