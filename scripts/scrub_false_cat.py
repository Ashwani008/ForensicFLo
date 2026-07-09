"""One-off cleanup: remove the false-positive 'cat' label produced by YOLOv8n
and BLIP hallucinations from a known set of caption files, then regenerate
SRT/VTT/JSON and rebuild the global index.

Verified manually (frame-by-frame inspection): none of the listed videos
contain a cat. The label came from low-confidence YOLO detections of small
objects and from BLIP image-captioning hallucinations.
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

# Stems whose 'cat' references were verified as false positives.
TARGET_STEMS = {
    "Video-009", "Video-041", "Video-042", "Video-043", "Video-044",
    "Video-045", "Video-046", "Video-047", "Video-144", "Video-145",
    "Video-150",
}

CAT_WORD = re.compile(r"\bcats?\b", re.IGNORECASE)
# Match ", <color> cat" or "<color> cat, " inside an "Objects: ..." list.
OBJ_ITEM = re.compile(r"(?:,\s*)?(?:[a-z]+\s+)?cats?(?=,|$)", re.IGNORECASE)


def _clean_text(text: str) -> str:
    # Drop 'gray cat' / 'orange cat' tokens inside the trailing 'Objects: ...'
    # phrase, then any bare 'cat' words elsewhere. Collapse stray commas.
    out = OBJ_ITEM.sub("", text)
    out = CAT_WORD.sub("", out)
    out = re.sub(r"Objects:\s*,\s*", "Objects: ", out)
    out = re.sub(r"\s*,\s*,", ",", out)
    out = re.sub(r"Objects:\s*$", "", out).rstrip(" .,")
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def _clean_segment(seg: dict) -> dict | None:
    if seg.get("kind") != "visual":
        return seg
    objs = [o for o in seg.get("objects", []) if "cat" not in o.lower()]
    text = _clean_text(seg.get("text", ""))
    if not text and not objs:
        return None  # drop empty visual segment
    new = dict(seg)
    new["text"] = text or "(visual)"
    if "objects" in seg:
        new["objects"] = objs
    return new


def main() -> None:
    changed = []
    for stem in sorted(TARGET_STEMS):
        jf = CAPTIONS_DIR / f"{stem}.json"
        if not jf.exists():
            print(f"[scrub] missing: {jf.name}")
            continue
        data = json.loads(jf.read_text(encoding="utf-8"))
        before = sum(1 for s in data["segments"] if "cat" in s.get("text", "").lower())
        new_segs = []
        for s in data["segments"]:
            cleaned = _clean_segment(s)
            if cleaned is not None:
                new_segs.append(cleaned)
        after = sum(1 for s in new_segs if "cat" in s.get("text", "").lower())
        caption_generator.write_captions(data["media"], new_segs, CAPTIONS_DIR)
        changed.append((jf.name, before, after))
        print(f"[scrub] {jf.name}: cat-mentions {before} -> {after}")

    print("[scrub] rebuilding index...")
    indexer.build_index(CAPTIONS_DIR, INDEX_FILE)
    print(f"[scrub] done. {len(changed)} file(s) cleaned.")


if __name__ == "__main__":
    main()
