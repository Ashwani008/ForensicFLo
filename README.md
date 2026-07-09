# Forensic-Search

> A standalone companion tool for **URUI**: generate **closed captions** (speech + non-speech sounds like *train, dog barking, siren*) for any audio/video file and **search your whole library by keyword** — clicking a result jumps straight to that timestamp in the built-in player.

Built for Hack2026. Runs 100% locally — no cloud, no API keys.

---

## What it does

1. **Speech-to-text** with OpenAI Whisper (local model).
2. **Non-speech sound tagging** with Google's YAMNet (AudioSet — 521 classes: train, dog, siren, applause, glass break, etc.).
3. Writes captions as `.srt` (standard), `.vtt` (for the browser `<track>` element), and `.json` (full segment data with `kind: speech|sound`).
4. Builds a single **keyword index** across every captioned file.
5. A small **Flask web UI** lets you:
   - search across all files by keyword,
   - see snippet + timestamp for every match,
   - click a match to open the player at that exact second with CC overlay,
   - browse/play any file in the library and follow along with synced captions.

---

## Project layout

```
Forensic-Search/
├── app.py                      # Flask web UI
├── config.py                   # Tweak model size, paths, thresholds
├── requirements.txt
├── forensic_search/
│   ├── audio_utils.py          # ffmpeg extraction
│   ├── transcriber.py          # Whisper speech-to-text
│   ├── sound_events.py         # YAMNet non-speech detection
│   ├── caption_generator.py    # SRT + VTT + JSON writers
│   ├── indexer.py              # Build + search keyword index
│   └── pipeline.py             # End-to-end per-file processing
├── scripts/
│   └── process_folder.py       # CLI batch processor
├── templates/                  # Jinja2 HTML
├── static/                     # CSS + JS
├── media/                      # ⬅ drop your audio/video files here
└── data/
    ├── captions/               # generated .srt / .vtt / .json
    └── index.json              # merged keyword index
```

---

## Setup (Windows / PowerShell)

```powershell
cd Forensic-Search

# 1. Python 3.10+ recommended
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Dependencies
pip install -r requirements.txt

# 3. ffmpeg must be on PATH (required by Whisper + audio extraction)
#    https://www.gyan.dev/ffmpeg/builds/ → add bin folder to PATH
ffmpeg -version
```

> **Note on sound events:** YAMNet needs TensorFlow. If you don't want it,
> set `ENABLE_SOUND_EVENTS = False` in `config.py` and skip the
> `tensorflow*` lines in `requirements.txt`. The tool still works — you'll
> just lose the `[train]` / `[dog]` / `[siren]` style captions.

---

## Use

### 1. Add media

Drop any `.mp3 .wav .m4a .flac .ogg .mp4 .mkv .mov .avi .webm` files into the `media/` folder.

### 2. Generate captions + index (CLI)

```powershell
python -m scripts.process_folder
# or point at a different folder
python -m scripts.process_folder C:\path\to\recordings
# bigger model = better accuracy, slower
python -m scripts.process_folder --model small
# skip sound-event tagging
python -m scripts.process_folder --no-events
```

### 3. Launch the web UI

```powershell
python app.py
# open http://127.0.0.1:5000
```

- Type **`train`** in the search box → every recording where a train was detected (or said) appears, each with a clickable timestamp.
- Click the timestamp → player opens, seeks to that moment, captions overlay.
- The **Process** button in the library re-runs the pipeline for one file (useful if you add a single new recording).
- **Reindex** rebuilds the keyword index from existing caption files.

---

## API (for integrating into URUI later)

| Endpoint                              | Description                                          |
|---------------------------------------|------------------------------------------------------|
| `GET  /api/search?q=train`            | JSON results grouped per file with match snippets    |
| `POST /api/process?name=<file>`       | Generate captions for one file in `media/`           |
| `POST /api/reindex`                   | Rebuild the keyword index                            |
| `GET  /captions/<stem>.vtt`           | WebVTT track (drop into URUI's `<video><track>`)     |
| `GET  /media/<name>`                  | Raw media (supports HTTP range requests)             |

This means once URUI is ready to integrate, the path is short:
1. Point URUI's player at `/captions/<stem>.vtt` for the caption track.
2. Add a keyword input that hits `/api/search` and shows results.

---

## Tunables (`config.py`)

| Setting                       | Default   | Meaning                                              |
|-------------------------------|-----------|------------------------------------------------------|
| `WHISPER_MODEL`               | `base`    | `tiny` (fastest) → `large` (most accurate)           |
| `WHISPER_LANGUAGE`            | `None`    | Force a language code or leave for auto-detect       |
| `ENABLE_SOUND_EVENTS`         | `True`    | Toggle YAMNet non-speech detection                   |
| `SOUND_EVENT_MIN_SCORE`       | `0.35`    | Confidence cutoff for a sound to be captioned        |
| `SOUND_EVENT_MIN_DURATION`    | `1.5`     | Drop blips shorter than this (sec) unless very confident |

---

## Example caption (JSON)

```json
{
  "media": "callwithjohn.mp4",
  "segments": [
    {"start": 0.0,  "end": 2.4, "kind": "speech", "text": "Hey John, can you hear me?"},
    {"start": 2.7,  "end": 5.1, "kind": "speech", "text": "Yeah loud and clear."},
    {"start": 11.2, "end": 14.9,"kind": "sound",  "text": "[train horn]"},
    {"start": 15.0, "end": 17.2,"kind": "speech", "text": "Sorry, a train is going by."}
  ]
}
```

A search for `train` would surface **both** the `[train horn]` sound event and the spoken sentence, each with its own jump-to timestamp.
