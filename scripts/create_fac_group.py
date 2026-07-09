"""
Create Security_Cam_Fac group:
  - Security_Cam_Building_001..008  -> Security_Cam_Fac_001..008
  - Security_Cam_Shop_001..005      -> Security_Cam_Fac_009..013
  - Security_Cam_Shop_018           -> Security_Cam_Fac_018
Update index.json and all caption files accordingly.
"""
import json
from pathlib import Path

BASE = Path(__file__).parent.parent
MEDIA_DIR   = BASE / "media"
CAP_DIR     = BASE / "data" / "captions"
INDEX_PATH  = BASE / "data" / "index.json"

# Build rename map: old_base -> new_base
rename_map = {}

for i in range(1, 9):          # Building 001-008 -> Fac 001-008
    rename_map[f"Security_Cam_Building_{i:03d}"] = f"Security_Cam_Fac_{i:03d}"

for i, fac_num in enumerate(range(9, 14), start=1):  # Shop 001-005 -> Fac 009-013
    rename_map[f"Security_Cam_Shop_{i:03d}"] = f"Security_Cam_Fac_{fac_num:03d}"

rename_map["Security_Cam_Shop_018"] = "Security_Cam_Fac_018"

print("Rename plan:")
for old, new in rename_map.items():
    print(f"  {old} -> {new}")

# ── 1. Rename media files ─────────────────────────────────────────────────────
print("\nRenaming media files...")
for old_base, new_base in rename_map.items():
    src = MEDIA_DIR / f"{old_base}.mp4"
    dst = MEDIA_DIR / f"{new_base}.mp4"
    if src.exists():
        src.rename(dst)
        print(f"  [media] {src.name} -> {dst.name}")
    else:
        print(f"  [MISSING] {src.name}")

# ── 2. Rename caption files ───────────────────────────────────────────────────
print("\nRenaming caption files...")
for old_base, new_base in rename_map.items():
    for ext in ("json", "srt", "vtt"):
        src = CAP_DIR / f"{old_base}.{ext}"
        dst = CAP_DIR / f"{new_base}.{ext}"
        if src.exists():
            src.rename(dst)
            print(f"  [captions] {src.name} -> {dst.name}")

# ── 3. Update index.json ──────────────────────────────────────────────────────
print("\nUpdating index.json...")
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    index = json.load(f)

updated = 0
for item in index.get("items", []):
    old_base = item["media"].replace(".mp4", "")
    if old_base in rename_map:
        new_base = rename_map[old_base]
        item["media"] = f"{new_base}.mp4"
        item["captions_json"] = f"{new_base}.json"
        print(f"  [index] {old_base} -> {new_base}")
        updated += 1

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False)

print(f"\nDone. {updated} index entries updated.")
