"""Forensic-Search web UI.

  GET  /                  -> library + search
  GET  /api/search?q=...  -> JSON search results
  GET  /api/reindex       -> rebuild the index from caption files
  POST /api/process       -> process one file from MEDIA_DIR (?name=foo.mp4)
  GET  /play/<name>       -> player page with CC overlay (?t=12.3 to seek)
  GET  /media/<name>      -> raw media stream
  GET  /captions/<name>   -> WebVTT track for the <video> element
"""
from __future__ import annotations
import re
import threading
import time
from pathlib import Path
from flask import (Flask, jsonify, render_template, request, send_from_directory,
                   abort)

import config
from forensic_search import indexer, pipeline
from forensic_search.audio_utils import get_ffmpeg

# Resolve ffmpeg up front (also injects its dir into PATH so Whisper finds it)
get_ffmpeg()

# Global cache so we don't load a 250-video JSON on every single search request
_GLOBAL_INDEX = None
def get_index():
    global _GLOBAL_INDEX
    if _GLOBAL_INDEX is None:
        _GLOBAL_INDEX = indexer.load_index(config.INDEX_FILE)
    return _GLOBAL_INDEX

app = Flask(__name__)

def auto_process_loop():
    """Background thread to automatically process new uncaptioned media."""
    while True:
        try:
            updated = False
            if config.MEDIA_DIR.exists():
                for p in sorted(config.MEDIA_DIR.iterdir()):
                    if p.is_file() and p.suffix.lower() in config.MEDIA_EXTS:
                        vtt = config.CAPTIONS_DIR / f"{p.stem}.vtt"
                        if not vtt.exists():
                            print(f"\n[auto-process] Detected new file: {p.name}")
                            pipeline.process_file(
                                p, config.CAPTIONS_DIR,
                                whisper_model=config.WHISPER_MODEL,
                                language=config.WHISPER_LANGUAGE,
                                enable_sound_events=config.ENABLE_SOUND_EVENTS,
                                min_score=config.SOUND_EVENT_MIN_SCORE,
                                min_duration=config.SOUND_EVENT_MIN_DURATION,
                                enable_visual=getattr(config, "ENABLE_VISUAL_OBJECTS", False),
                                visual_sample_sec=getattr(config, "VISUAL_SAMPLE_SEC", 2.0),
                                visual_yolo_model=getattr(config, "VISUAL_YOLO_MODEL", "yolov8n.pt"),
                                visual_yolo_conf=getattr(config, "VISUAL_YOLO_CONF", 0.35),
                                visual_blip_model=getattr(config, "VISUAL_BLIP_MODEL", "Salesforce/blip-image-captioning-base")
                            )
                            updated = True
            if updated:
                print("[auto-process] Rebuilding index...")
                indexer.build_index(config.CAPTIONS_DIR, config.INDEX_FILE)
        except Exception as e:
            print(f"[auto-process] Error: {e}")
        time.sleep(5)

# Start auto-processor if not disabled
import os
if not os.environ.get("DISABLE_AUTO_PROCESS"):
    threading.Thread(target=auto_process_loop, daemon=True).start()


@app.after_request
def no_cache(response):
    """Prevent browsers from caching HTML/JS/CSS responses."""
    if request.path.startswith("/media/") or request.path.startswith("/captions/"):
        return response  # allow media range-request caching
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _list_media():
    import datetime
    import json

    out = []
    if not config.MEDIA_DIR.exists():
        return out

    for p in sorted(config.MEDIA_DIR.iterdir()):
        if not (p.is_file() and p.suffix.lower() in config.MEDIA_EXTS):
            continue

        vtt = config.CAPTIONS_DIR / f"{p.stem}.vtt"
        if not vtt.exists():
            continue

        mtime = p.stat().st_mtime
        capture_dt = datetime.datetime.fromtimestamp(mtime)
        media_type = "Video" if p.suffix.lower() in config.VIDEO_EXTS else "Audio"
        duration_str = "-"

        cap_json = config.CAPTIONS_DIR / f"{p.stem}.json"
        if cap_json.exists():
            try:
                data = json.loads(cap_json.read_text(encoding="utf-8"))
                ends = [float(s.get("end", 0)) for s in data.get("segments", [])]
                if ends:
                    secs = int(max(ends))
                    duration_str = f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"
            except Exception:
                pass

        out.append({
            "name": p.name,
            "stem": p.stem,
            "captioned": True,
            "ext": p.suffix.lower(),
            "capture_date": capture_dt.strftime("%m/%d/%Y %H:%M:%S"),
            "capture_date_iso": capture_dt.strftime("%Y-%m-%d"),
            "duration": duration_str,
            "media_type": media_type,
        })

    return out


@app.route("/")
def home():
    return render_template("index.html", media=_list_media())


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    # Multi-keyword (tag) search: split on commas (or newlines).
    keywords = [k.strip() for k in re.split(r"[,\n]+", q) if k.strip()]
    # Optional scope: comma-separated list of media filenames to search.
    scope_raw = request.args.get("media", "").strip()
    scope = {s.strip() for s in scope_raw.split(",") if s.strip()}
    # Optional kind filter: comma-separated subset of {speech, sound, visual}.
    kinds_raw = request.args.get("kinds", "").strip()
    kinds = {k.strip().lower() for k in kinds_raw.split(",") if k.strip()} or None
    
    # Use cached index in Cloud Run
    index = get_index()
    
    if scope:
        index = {"items": [it for it in index.get("items", [])
                            if it.get("media") in scope]}
    results = indexer.search(
        index, keywords,
        expand=getattr(config, "ENABLE_NLP_EXPANSION", True),
        kinds=kinds,
    ) if keywords else []
    return jsonify({"query": q, "keywords": keywords, "scope": sorted(scope),
                    "kinds": sorted(kinds) if kinds else [],
                    "result_count": len(results), "results": results})


@app.route("/api/reindex", methods=["GET", "POST"])
def api_reindex():
    indexer.build_index(config.CAPTIONS_DIR, config.INDEX_FILE)
    return jsonify({"ok": True, "media": _list_media()})


@app.route("/api/process", methods=["POST"])
def api_process():
    name = request.args.get("name") or (request.json or {}).get("name")
    if not name:
        return jsonify({"ok": False, "error": "missing 'name'"}), 400
    src = config.MEDIA_DIR / name
    if not src.exists():
        return jsonify({"ok": False, "error": "file not found"}), 404
    meta = pipeline.process_file(
        src, config.CAPTIONS_DIR,
        whisper_model=config.WHISPER_MODEL,
        language=config.WHISPER_LANGUAGE,
        enable_sound_events=config.ENABLE_SOUND_EVENTS,
        min_score=config.SOUND_EVENT_MIN_SCORE,
        min_duration=config.SOUND_EVENT_MIN_DURATION,
        enable_visual=getattr(config, "ENABLE_VISUAL_OBJECTS", False),
        visual_sample_sec=getattr(config, "VISUAL_SAMPLE_SEC", 2.0),
        visual_yolo_model=getattr(config, "VISUAL_YOLO_MODEL", "yolov8n.pt"),
        visual_yolo_conf=getattr(config, "VISUAL_YOLO_CONF", 0.35),
        visual_blip_model=getattr(config, "VISUAL_BLIP_MODEL",
                                  "Salesforce/blip-image-captioning-base"),
    )
    indexer.build_index(config.CAPTIONS_DIR, config.INDEX_FILE)
    return jsonify({"ok": True, "meta": {k: v for k, v in meta.items() if k != "segments"}})


@app.route("/play/<path:name>")
def play(name):
    src = config.MEDIA_DIR / name
    if not src.exists():
        abort(404)
    is_video = src.suffix.lower() in {".mp4", ".mkv", ".mov", ".avi", ".webm"}
    vtt_exists = (config.CAPTIONS_DIR / f"{src.stem}.vtt").exists()
    start = request.args.get("t", "0")
    try:
        start = float(start)
    except ValueError:
        start = 0.0
    return render_template("player.html", name=name, stem=src.stem,
                           is_video=is_video, vtt_exists=vtt_exists, start=start)


@app.route("/media/<path:name>")
def media(name):
    return send_from_directory(config.MEDIA_DIR, name, conditional=True)


@app.route("/captions/<path:name>")
def captions(name):
    # name is the stem + .vtt
    return send_from_directory(config.CAPTIONS_DIR, name, mimetype="text/vtt")


if __name__ == "__main__":
    print(f"Forensic-Search running at http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=False)
