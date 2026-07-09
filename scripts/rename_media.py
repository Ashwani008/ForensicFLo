"""
Rename Video-XXX files to realistic camera source names and update index.json + captions.
"""
import os, json, shutil
from pathlib import Path

BASE = Path(__file__).parent.parent

# ── Camera type groups (total = 158) ──────────────────────────────────────────
# Format: (prefix, count)
GROUPS = [
    ("Security_Cam_Street",    20),  # 001-020
    ("Body_Worn_Cam",          18),  # 021-038
    ("Security_Cam_Building",  20),  # 039-058
    ("Security_Cam_Parking",   15),  # 059-073
    ("Dash_Cam",               17),  # 074-090
    ("Security_Cam_Lobby",     16),  # 091-106
    ("Security_Cam_Alley",     15),  # 107-121
    ("CCTV_Town_Centre",       17),  # 122-138
    ("Security_Cam_Shop",      20),  # 139-158
]

# Build old→new mapping
mapping = {}  # "Video-001" -> "Security_Cam_Street_001"
n = 1
for prefix, count in GROUPS:
    for i in range(1, count + 1):
        old_base = f"Video-{n:03d}"
        new_base = f"{prefix}_{i:03d}"
        mapping[old_base] = new_base
        n += 1

print(f"Mapping covers {len(mapping)} files\n")

# ── 1. Rename media files ──────────────────────────────────────────────────────
media_dir = BASE / "media"
renamed_media = 0
for old_base, new_base in mapping.items():
    old_path = media_dir / f"{old_base}.mp4"
    new_path = media_dir / f"{new_base}.mp4"
    if old_path.exists() and not new_path.exists():
        old_path.rename(new_path)
        renamed_media += 1
print(f"Media files renamed: {renamed_media}")

# ── 2. Rename caption files (.json, .srt, .vtt) ───────────────────────────────
captions_dir = BASE / "data" / "captions"
renamed_captions = 0
for old_base, new_base in mapping.items():
    for ext in ("json", "srt", "vtt"):
        old_path = captions_dir / f"{old_base}.{ext}"
        new_path = captions_dir / f"{new_base}.{ext}"
        if old_path.exists() and not new_path.exists():
            old_path.rename(new_path)
            renamed_captions += 1
print(f"Caption files renamed: {renamed_captions}")

# ── 3. Update data/index.json ─────────────────────────────────────────────────
index_path = BASE / "data" / "index.json"
with open(index_path, "r", encoding="utf-8") as f:
    index = json.load(f)

updated = 0
for item in index.get("items", []):
    old_media = item.get("media", "")
    old_base = old_media.replace(".mp4", "")
    if old_base in mapping:
        new_base = mapping[old_base]
        item["media"] = f"{new_base}.mp4"
        item["captions_json"] = f"{new_base}.json"
        updated += 1

with open(index_path, "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False)

print(f"index.json entries updated: {updated}")
print("\nDone! Rename mapping summary:")
for prefix, count in GROUPS:
    print(f"  {prefix}: {count} files")
