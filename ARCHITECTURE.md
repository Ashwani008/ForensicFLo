# Forensic-Search Architecture

## 1. Purpose and Scope

Forensic-Search is a local-first forensic media analysis and retrieval system. It processes audio and video files into time-aligned captions, enriches them with non-speech sound events and visual descriptions, and provides keyword search with timestamp-level playback.

The system is designed for:
- Offline operation (no cloud inference required)
- Analyst workflows over a file-based media library
- Fast iteration from ingestion to searchable evidence

Primary outcomes:
- Unified searchable timeline across speech, sound, and visual modalities
- Click-to-seek playback from search results
- Reproducible local artifacts in standard caption formats

## 2. Architectural Style

The project follows a modular monolith architecture with clear pipeline stages:
- Presentation layer: Flask + Jinja templates + vanilla JavaScript
- Application layer: route orchestration + background auto-processing loop
- Domain processing layer: transcription, sound event detection, visual analysis, caption generation
- Data/index layer: file-based JSON index and caption artifacts

This architecture favors simplicity and local operability over distributed complexity.

## 3. Context Diagram (System Boundary)

External actors and systems:
- Analyst: searches, plays media, triggers processing/reindexing
- File system media drop: new files placed in media directory
- Local ML runtimes: Whisper, TensorFlow Hub YAMNet, Ultralytics YOLO, Hugging Face BLIP
- ffmpeg/ffprobe binaries: media decoding, stream inspection, frame extraction

Forensic-Search boundary responsibilities:
- Detect unprocessed media
- Produce caption artifacts (.srt, .vtt, .json)
- Build and query merged search index
- Serve media and captions for browser playback

## 4. Runtime Components

### 4.1 Web Application Host

Source: app.py

Responsibilities:
- Boots Flask application
- Resolves ffmpeg at startup
- Starts a daemon thread for continuous auto-processing
- Exposes API and page routes
- Applies no-cache headers for HTML/JS/CSS responses

Key routes:
- GET /: library + search view
- GET /api/search: keyword search endpoint with optional media scope and modality filter
- GET|POST /api/reindex: rebuilds merged index from caption JSON files
- POST /api/process: processes one selected media file
- GET /play/<name>: dedicated player page with optional seek time
- GET /media/<name>: media streaming endpoint
- GET /captions/<name>: WebVTT caption serving endpoint

### 4.2 Processing Orchestrator

Source: forensic_search/pipeline.py

Responsibilities:
- Coordinates end-to-end file processing in deterministic order
- Extracts audio to normalized mono WAV
- Runs speech transcription
- Optionally runs sound event detection
- Optionally runs visual analysis for video files
- Merges all segments and writes caption outputs
- Ensures temporary WAV cleanup via finally block

Processing order for one file:
1. extract_audio
2. transcribe
3. detect_events (optional)
4. analyze_video (optional for video)
5. write_captions

### 4.3 Audio Extraction and ffmpeg Resolution

Source: forensic_search/audio_utils.py

Responsibilities:
- Locates ffmpeg from environment, PATH, or known locations
- Injects ffmpeg directory into PATH for downstream libraries
- Checks audio stream presence via ffprobe (or ffmpeg fallback)
- Produces silent fallback WAV for video files with no audio stream

Design intent:
- Avoid hard failures in downstream speech/sound stages for silent media

### 4.4 Speech Transcription

Source: forensic_search/transcriber.py

Responsibilities:
- Lazy-loads Whisper model by name and caches singleton instances
- Transcribes WAV into timestamped speech segments
- Emits normalized segment schema with kind set to speech

### 4.5 Non-Speech Sound Event Detection

Source: forensic_search/sound_events.py

Responsibilities:
- Lazy-loads YAMNet from TensorFlow Hub
- Scores frame-level sound classes
- Filters speech-like and low-signal background classes
- Merges adjacent events and prunes low-duration/low-confidence noise
- Emits segments with bracketed labels, kind set to sound

### 4.6 Visual Analysis

Source: forensic_search/visual.py

Responsibilities:
- Samples video frames at configurable interval using ffmpeg
- Runs YOLOv8 object detection (lazy-loaded)
- Infers coarse object color from inner bounding-box pixels
- Runs BLIP captioning (lazy-loaded)
- Merges adjacent identical visual descriptors
- Emits visual segments with optional object lists

Fallback behavior:
- If YOLO and BLIP are both unavailable, returns no visual segments without hard failure

### 4.7 Caption Artifact Generation

Source: forensic_search/caption_generator.py

Responsibilities:
- Produces .srt and .vtt overlays from non-visual segments only
- Produces .json with all segments including visual entries
- Keeps visual metadata searchable without cluttering on-screen captions

### 4.8 Index Build and Search

Source: forensic_search/indexer.py

Responsibilities:
- Builds merged index by scanning all caption JSON files
- Loads index into memory for query-time matching
- Supports single or multi-keyword queries
- Optional NLP expansion per keyword
- Optional modality filter (speech/sound/visual)
- Returns file-grouped results with contextual snippets

Search semantics:
- Multi-keyword uses intersection (AND at file level): every keyword must match at least once in a file
- Result ranking by descending match count

### 4.9 NLP Keyword Expansion

Source: forensic_search/nlp_search.py

Responsibilities:
- Lazy-loads NLTK WordNet and lemmatizer
- Expands each query term with lemma and synonym variants
- Caches expansion results to reduce repeated lookup cost
- Gracefully falls back to exact keyword when resources unavailable

### 4.10 Batch and Maintenance Scripts

Sources:
- scripts/process_folder.py
- scripts/patch_colours.py

Responsibilities:
- Batch process media directory from CLI with flags for model/language/features
- Rebuild index after batch run
- Retroactively patch visual color/object annotations where needed

## 5. Data Model and Storage

### 5.1 Directory-Level Data Stores

- media/: source audio/video files
- data/captions/: generated per-file artifacts (.srt, .vtt, .json)
- data/index.json: merged cross-file searchable index

### 5.2 Canonical Segment Schema

Each segment in JSON caption files follows:
- start: float seconds
- end: float seconds
- text: caption/event text
- kind: speech | sound | visual
- objects: optional list, usually for visual segments

### 5.3 Overlay vs Search Representation

- Overlay track (.srt/.vtt): speech + sound only
- Search corpus (.json index): speech + sound + visual

This split improves playback readability while preserving maximal retrieval metadata.

## 6. Core Flows

### 6.1 Automatic Ingestion Flow

1. Background loop scans media directory every 5 seconds
2. For each supported file without matching .vtt, run pipeline processing
3. If at least one file processed in scan cycle, rebuild merged index

### 6.2 Manual Single-File Processing Flow

1. Client calls POST /api/process with file name
2. Server runs orchestrator for that file
3. Server rebuilds index
4. Response returns metadata counts and artifact paths

### 6.3 Search Flow

1. Client sends query with optional media scope and kind filters
2. Server tokenizes query into keywords
3. Optional NLP expansion generates variant terms
4. Regex matching runs across indexed segment text
5. Files satisfying all keyword patterns are returned with snippets and timestamps

### 6.4 Playback Flow

1. User opens player route or floating player
2. Browser loads media stream and VTT track
3. JS parser builds cue list and sync logic
4. Clicking a cue or search timestamp seeks media to exact time

## 7. Technology Stack

Backend:
- Python 3.x
- Flask
- ffmpeg/ffprobe integration

ML/AI:
- OpenAI Whisper for speech-to-text
- TensorFlow Hub YAMNet for sound events
- Ultralytics YOLOv8 for object detection
- Hugging Face BLIP for scene captioning
- NLTK WordNet for lexical expansion

Frontend:
- Jinja2 templates
- Vanilla JavaScript
- CSS custom styling

## 8. Design Decisions and Tradeoffs

### 8.1 File-Based Persistence Over Database

Why:
- Zero external infrastructure
- Easy portability and inspection

Tradeoff:
- Full index rebuilds on updates are O(number of caption files)

### 8.2 Local-Only Model Inference

Why:
- Privacy and offline operation
- No API keys and predictable local data governance

Tradeoff:
- CPU-bound latency can be high for long videos or visual-heavy processing

### 8.3 Monolithic Service with Background Thread

Why:
- Minimal deployment complexity
- Simple local development and demo flow

Tradeoff:
- Limited concurrency and no explicit job queue semantics

### 8.4 Visual Metadata Kept Out of Overlay Captions

Why:
- Better live readability for users during playback

Tradeoff:
- Visual insights are visible through search and JSON, not subtitle overlay by default

## 9. Non-Functional Characteristics

Performance:
- Throughput depends heavily on selected Whisper model and whether visual analysis is enabled
- Index search is in-memory and generally fast for small-to-medium local libraries

Reliability:
- Multiple graceful-degradation points (missing optional ML dependencies)
- Temporary audio artifacts cleaned in orchestrator finally block

Portability:
- Cross-platform Python stack, but ffmpeg path discovery includes Windows-specific fallbacks

Maintainability:
- Clear module boundaries by processing concern
- Config-driven feature toggles in config.py

## 10. Security and Privacy Posture

Current posture:
- Designed for localhost usage
- No authentication or authorization layer
- Media and captions are served directly from local directories

Implications:
- Should not be exposed directly to untrusted networks without perimeter controls

Recommended hardening path:
- Add authn/authz (reverse proxy or app-level)
- Restrict process/reindex endpoints by role
- Introduce structured audit logs for processing/search actions

## 11. Scalability Considerations

Current bottlenecks:
- Sequential file processing
- Full index rebuild on each processing update
- CPU-heavy visual captioning and object detection

Scalable evolution options:
- Incremental index updates per changed caption file
- Persistent job queue for processing tasks
- Worker pool for parallel processing
- Optional DB-backed index for larger corpora
- Device-aware model scheduling (CPU/GPU)

## 12. Observability and Operations

Current observability:
- Console logs with stage-level messages

Recommended additions:
- Structured logging with request and job correlation IDs
- Basic metrics (processing duration, queue depth, index rebuild time)
- Health and readiness endpoints

## 13. Extension Points

Near-term extension opportunities:
- Semantic search/reranking over caption corpus
- Query operators for OR/NOT/proximity/time windows
- In-browser upload and ingestion workflow
- Case/workspace partitioning for multi-tenant forensic usage
- Export packages for evidence handoff

## 14. Architecture Summary

Forensic-Search is a pragmatic local forensic retrieval platform built as a modular Python monolith. Its architecture is centered on a deterministic, multi-modal processing pipeline and a file-backed searchable index, exposed through a lightweight web UI optimized for investigator workflows. The current design maximizes deployability and transparency, with clear paths to evolve toward higher scale, stronger security, and richer retrieval intelligence.