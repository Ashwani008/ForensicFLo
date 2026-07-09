"""Remove false-positive object labels from visual segments in caption files,
then regenerate SRT/VTT/JSON and rebuild the global index.

Usage (from repo root):
    python scripts/scrub_label.py <label> <stem1> <stem2> ...

Only segments with kind == "visual" are touched. Speech segments are never
modified. Useful for cleaning up known YOLOv8n / BLIP hallucinations after
manual frame-by-frame verification.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forensic_search import caption_generator, indexer  # noqa: E402

CAPTIONS_DIR = ROOT / "data" / "captions"
INDEX_FILE = ROOT / "data" / "index.json"


def _build_patterns(label: str):
    # Match the bare word (and a trailing 's' plural) and any '<color> label'
    # token inside an "Objects: ..." list.
    word = re.compile(rf"\b{re.escape(label)}s?\b", re.IGNORECASE)
    obj_item = re.compile(
        rf"(?:,\s*)?(?:[a-z]+\s+)?{re.escape(label)}s?(?=,|$)",
        re.IGNORECASE,
    )
    return word, obj_item


def _clean_text(text: str, word_re: re.Pattern, obj_re: re.Pattern) -> str:
    out = obj_re.sub("", text)
    out = word_re.sub("", out)
    out = re.sub(r"Objects:\s*,\s*", "Objects: ", out)
    out = re.sub(r"\s*,\s*,", ",", out)
    out = re.sub(r"Objects:\s*$", "", out).rstrip(" .,")
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def _clean_segment(seg: dict, label: str, word_re, obj_re) -> dict | None:
    if seg.get("kind") != "visual":
        return seg
    objs = [o for o in seg.get("objects", []) if label not in o.lower()]
    text = _clean_text(seg.get("text", ""), word_re, obj_re)
    if not text and not objs:
        return None
    new = dict(seg)
    new["text"] = text or "(visual)"
    if "objects" in seg:
        new["objects"] = objs
    return new


def scrub(label: str, stems: list[str]) -> None:
    label = label.lower()
    word_re, obj_re = _build_patterns(label)
    for stem in stems:
        jf = CAPTIONS_DIR / f"{stem}.json"
        if not jf.exists():
            print(f"[scrub] missing: {jf.name}")
            continue
        data = json.loads(jf.read_text(encoding="utf-8"))
        before = sum(1 for s in data["segments"]
                     if word_re.search(s.get("text", "")))
        new_segs = []
        for s in data["segments"]:
            cleaned = _clean_segment(s, label, word_re, obj_re)
            if cleaned is not None:
                new_segs.append(cleaned)
        after = sum(1 for s in new_segs if word_re.search(s.get("text", "")))
        caption_generator.write_captions(data["media"], new_segs, CAPTIONS_DIR)
        print(f"[scrub] {jf.name}: '{label}' mentions {before} -> {after}")

    print("[scrub] rebuilding index...")
    indexer.build_index(CAPTIONS_DIR, INDEX_FILE)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python scripts/scrub_label.py <label> <stem1> [stem2 ...]",
              file=sys.stderr)
        sys.exit(2)
    scrub(sys.argv[1], sys.argv[2:])
