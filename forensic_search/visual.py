"""Visual analysis: sample frames from a video and turn each into searchable
text via YOLOv8 (object labels) + BLIP (natural-language caption).

All heavy ML dependencies are lazy-imported so the rest of the app keeps
working even if `ultralytics` / `transformers` / `torch` aren't installed.
"""
from __future__ import annotations
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from .audio_utils import get_ffmpeg


# ---- lazy model singletons --------------------------------------------------
_YOLO = None
_YOLO_TRIED = False
_BLIP = None  # tuple (processor, model)
_BLIP_TRIED = False


def _load_yolo(model_name: str):
    global _YOLO, _YOLO_TRIED
    if _YOLO_TRIED:
        return _YOLO
    _YOLO_TRIED = True
    try:
        from ultralytics import YOLO  # type: ignore
        print(f"[visual] loading YOLO model: {model_name}")
        _YOLO = YOLO(model_name)
    except Exception as ex:
        print(f"[visual] YOLO unavailable ({ex.__class__.__name__}: {ex}); "
              "objects will be skipped.")
        _YOLO = None
    return _YOLO


def _load_blip(model_name: str):
    global _BLIP, _BLIP_TRIED
    if _BLIP_TRIED:
        return _BLIP
    _BLIP_TRIED = True
    try:
        from transformers import BlipProcessor, BlipForConditionalGeneration  # type: ignore
        print(f"[visual] loading BLIP model: {model_name}")
        processor = BlipProcessor.from_pretrained(model_name)
        model = BlipForConditionalGeneration.from_pretrained(model_name)
        model.eval()
        _BLIP = (processor, model)
    except Exception as ex:
        print(f"[visual] BLIP unavailable ({ex.__class__.__name__}: {ex}); "
              "captions will be skipped.")
        _BLIP = None
    return _BLIP


# ---- frame sampling ---------------------------------------------------------
def sample_frames(media_path: Path, every_sec: float,
                  out_dir: Path) -> List[Tuple[float, Path]]:
    """Dump one JPEG every `every_sec` using ffmpeg. Returns [(timestamp, path)]."""
    ffmpeg = get_ffmpeg()
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%06d.jpg"
    fps_expr = f"1/{every_sec}"
    cmd = [
        ffmpeg, "-y", "-i", str(media_path),
        "-vf", f"fps={fps_expr}",
        "-q:v", "4",
        str(pattern),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    frames = sorted(out_dir.glob("frame_*.jpg"))
    # ffmpeg fps filter places frame i (1-indexed) roughly at t = (i-1) * every_sec.
    return [((i - 1) * every_sec, p) for i, p in enumerate(frames, 1)]


# ---- color detection --------------------------------------------------------
def _rgb_to_color_name(r: int, g: int, b: int) -> str:
    """Map an average RGB value to a basic color name via HSV."""
    r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
    max_c = max(r_n, g_n, b_n)
    min_c = min(r_n, g_n, b_n)
    delta = max_c - min_c
    v = max_c
    s = (delta / max_c) if max_c > 0 else 0

    if s < 0.18:
        if v < 0.25:
            return "black"
        if v > 0.78:
            return "white"
        return "gray"

    if delta == 0:
        h = 0.0
    elif max_c == r_n:
        h = 60.0 * (((g_n - b_n) / delta) % 6)
    elif max_c == g_n:
        h = 60.0 * ((b_n - r_n) / delta + 2)
    else:
        h = 60.0 * ((r_n - g_n) / delta + 4)

    if v < 0.2:
        return "black"
    if h < 15 or h >= 345:
        return "red"
    if h < 45:
        return "orange"
    if h < 75:
        return "yellow"
    if h < 165:
        return "green"
    if h < 195:
        return "cyan"
    if h < 255:
        return "blue"
    if h < 285:
        return "purple"
    if h < 345:
        return "pink"
    return "red"


def _get_object_color(frame_path: Path, box: List[float]) -> Optional[str]:
    """Return the dominant color name for the object inside the given bounding box."""
    try:
        from PIL import Image  # type: ignore
        img = Image.open(frame_path).convert("RGB")
        x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
        # Use the inner 70% of the box to reduce background contamination
        pad_x = max(1, int((x2 - x1) * 0.15))
        pad_y = max(1, int((y2 - y1) * 0.15))
        crop = img.crop((
            max(0, x1 + pad_x), max(0, y1 + pad_y),
            min(img.width, x2 - pad_x), min(img.height, y2 - pad_y),
        ))
        if crop.width < 4 or crop.height < 4:
            return None
        crop = crop.resize((16, 16), Image.LANCZOS)
        pixels = list(crop.getdata())
        # Filter near-black and near-white pixels (likely shadows / overexposure)
        filtered = [p for p in pixels if not (p[0] < 30 and p[1] < 30 and p[2] < 30)
                    and not (p[0] > 225 and p[1] > 225 and p[2] > 225)]
        if not filtered:
            filtered = pixels
        r = int(sum(p[0] for p in filtered) / len(filtered))
        g = int(sum(p[1] for p in filtered) / len(filtered))
        b = int(sum(p[2] for p in filtered) / len(filtered))
        return _rgb_to_color_name(r, g, b)
    except Exception:
        return None


# ---- inference --------------------------------------------------------------
def detect_objects(frame_paths: List[Path], model, conf: float) -> List[List[str]]:
    if model is None or not frame_paths:
        return [[] for _ in frame_paths]
    out: List[List[str]] = []
    try:
        results = model.predict([str(p) for p in frame_paths],
                                conf=conf, verbose=False)
        for r, frame_path in zip(results, frame_paths):
            names = r.names if hasattr(r, "names") else {}
            # Collect per-class bounding boxes (keep first/largest box per class)
            class_boxes: dict = {}
            if getattr(r, "boxes", None) is not None and r.boxes is not None:
                cls_tensor = r.boxes.cls
                xyxy_tensor = r.boxes.xyxy
                if cls_tensor is not None and xyxy_tensor is not None:
                    for i, c in enumerate(cls_tensor.tolist()):
                        name = names.get(int(c), str(int(c)))
                        box = xyxy_tensor[i].tolist()
                        # Keep the largest box per class (by area)
                        area = (box[2] - box[0]) * (box[3] - box[1])
                        if name not in class_boxes or area > class_boxes[name][1]:
                            class_boxes[name] = (box, area)

            labels: set = set()
            for obj_name, (box, _) in class_boxes.items():
                color = _get_object_color(frame_path, box)
                if color:
                    labels.add(f"{color} {obj_name}")
                else:
                    labels.add(obj_name)
            out.append(sorted(labels))
    except Exception as ex:
        print(f"[visual] YOLO predict failed: {ex}")
        return [[] for _ in frame_paths]
    return out


def caption_frames(frame_paths: List[Path], blip) -> List[str]:
    if blip is None or not frame_paths:
        return ["" for _ in frame_paths]
    processor, model = blip
    try:
        from PIL import Image  # type: ignore
        import torch  # type: ignore
    except Exception as ex:
        print(f"[visual] BLIP runtime deps missing: {ex}")
        return ["" for _ in frame_paths]

    captions: List[str] = []
    for p in frame_paths:
        try:
            img = Image.open(p).convert("RGB")
            inputs = processor(images=img, return_tensors="pt")
            with torch.no_grad():
                out_ids = model.generate(**inputs, max_new_tokens=40)
            text = processor.decode(out_ids[0], skip_special_tokens=True).strip()
            captions.append(text)
        except Exception as ex:
            print(f"[visual] BLIP caption failed for {p.name}: {ex}")
            captions.append("")
    return captions


# ---- top-level orchestration ------------------------------------------------
def _build_text(caption: str, objects: List[str]) -> str:
    parts = []
    if caption:
        parts.append(caption.rstrip(". "))
    if objects:
        parts.append("Objects: " + ", ".join(objects))
    return ". ".join(parts).strip()


def analyze_video(media_path: Path,
                  every_sec: float = 2.0,
                  yolo_model: str = "yolov8n.pt",
                  yolo_conf: float = 0.35,
                  blip_model: str = "Salesforce/blip-image-captioning-base"
                  ) -> List[Dict[str, Any]]:
    """Return segments [{start, end, text, kind:'visual', objects}].

    Adjacent frames with identical caption + object set are merged into one
    segment. Returns [] (with a warning) when no ML model is available.
    """
    yolo = _load_yolo(yolo_model)
    blip = _load_blip(blip_model)
    if yolo is None and blip is None:
        return []

    tmp_dir = Path(tempfile.mkdtemp(prefix="fs_frames_"))
    try:
        print(f"[visual] {media_path.name}: sampling frames every {every_sec}s...")
        frames = sample_frames(media_path, every_sec, tmp_dir)
        if not frames:
            return []
        paths = [p for _, p in frames]
        print(f"[visual] {media_path.name}: analyzing {len(paths)} frame(s)...")
        objs = detect_objects(paths, yolo, yolo_conf)
        caps = caption_frames(paths, blip)

        segments: List[Dict[str, Any]] = []
        for (t, _), caption, objects in zip(frames, caps, objs):
            text = _build_text(caption, objects)
            if not text:
                continue
            start = round(t, 2)
            end = round(t + every_sec, 2)
            if segments:
                prev = segments[-1]
                if prev["text"] == text and prev["end"] >= start - 0.001:
                    prev["end"] = end
                    continue
            segments.append({
                "start": start,
                "end": end,
                "text": text,
                "kind": "visual",
                "objects": objects,
            })
        print(f"[visual] {media_path.name}: produced {len(segments)} visual segment(s)")
        return segments
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
