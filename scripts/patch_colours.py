"""Batch-patch all processed videos with colour-aware YOLO object labels.

Re-runs YOLO (fast) on every video that already has visual segments,
reuses the existing BLIP captions, and skips Whisper entirely.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

# Make sure the project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from forensic_search.audio_utils import get_ffmpeg
from forensic_search.visual import _get_object_color, _load_yolo, sample_frames
from forensic_search import caption_generator, indexer

get_ffmpeg()
yolo = _load_yolo(config.VISUAL_YOLO_MODEL)
every_sec = config.VISUAL_SAMPLE_SEC


def build_text(caption: str, objects: list) -> str:
    parts = []
    if caption:
        parts.append(caption.rstrip(". "))
    if objects:
        parts.append(", ".join(objects))
    return ". ".join(parts).strip()


patched_total = 0

for json_path in sorted(config.CAPTIONS_DIR.glob("*.json")):
    data = json.loads(json_path.read_text(encoding="utf-8"))
    visual_segs = [s for s in data["segments"] if s.get("kind") == "visual"]
    if not visual_segs:
        continue

    media_name = data["media"]
    media_path = config.MEDIA_DIR / media_name
    if not media_path.exists():
        print(f"[skip] media not found: {media_name}")
        continue

    # Build lookup: rounded start_time -> existing BLIP caption text
    caption_lookup: dict = {}
    for s in visual_segs:
        raw = s["text"]
        blip_caption = raw.split(". Objects:")[0]
        caption_lookup[round(s["start"], 2)] = blip_caption

    tmp_dir = Path(tempfile.mkdtemp(prefix="fs_patch_"))
    try:
        frames = sample_frames(media_path, every_sec, tmp_dir)
        if not frames:
            continue
        paths = [p for _, p in frames]

        results = yolo.predict(
            [str(p) for p in paths],
            conf=config.VISUAL_YOLO_CONF,
            verbose=False,
        )

        new_visual: list = []
        for (t, frame_path), r in zip(frames, results):
            names = r.names if hasattr(r, "names") else {}
            class_boxes: dict = {}
            if getattr(r, "boxes", None) is not None and r.boxes is not None:
                cls_t = r.boxes.cls
                xyxy_t = r.boxes.xyxy
                if cls_t is not None and xyxy_t is not None:
                    for i, c in enumerate(cls_t.tolist()):
                        name = names.get(int(c), str(int(c)))
                        box = xyxy_t[i].tolist()
                        area = (box[2] - box[0]) * (box[3] - box[1])
                        if name not in class_boxes or area > class_boxes[name][1]:
                            class_boxes[name] = (box, area)

            colored: list = []
            for obj_name, (box, _) in class_boxes.items():
                color = _get_object_color(frame_path, box)
                colored.append(f"{color} {obj_name}" if color else obj_name)
            colored = sorted(colored)

            caption = caption_lookup.get(round(t, 2), "")
            text = build_text(caption, colored)
            if not text:
                continue

            start = round(t, 2)
            end = round(t + every_sec, 2)
            if (
                new_visual
                and new_visual[-1]["text"] == text
                and new_visual[-1]["end"] >= start - 0.001
            ):
                new_visual[-1]["end"] = end
            else:
                new_visual.append(
                    {
                        "start": start,
                        "end": end,
                        "text": text,
                        "kind": "visual",
                        "objects": colored,
                    }
                )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    non_visual = [s for s in data["segments"] if s.get("kind") != "visual"]
    data["segments"] = sorted(
        non_visual + new_visual, key=lambda s: s["start"]
    )
    json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    caption_generator.write_captions(
        data["media"], data["segments"], config.CAPTIONS_DIR
    )
    patched_total += 1
    print(f"[ok] {json_path.name}  ({len(new_visual)} visual segs)")

indexer.build_index(config.CAPTIONS_DIR, config.INDEX_FILE)
print(f"\nDone. Patched {patched_total} file(s).")
