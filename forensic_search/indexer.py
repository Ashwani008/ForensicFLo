"""Builds and queries the global keyword index using a precomputed JSON structure."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import List, Dict, Any

def build_index(captions_dir: Path, index_file: Path) -> Dict[str, Any]:
    """Scan every *.json caption file and write a merged index."""
    items = []
    for jf in sorted(captions_dir.glob("*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as ex:
            print(f"[index] skip {jf.name}: {ex}")
            continue
        items.append({
            "media": data["media"],
            "captions_json": jf.name,
            "segments": data.get("segments", []),
        })
    index = {"items": items}
    index_file.write_text(json.dumps(index, separators=(',', ':')), encoding="utf-8")
    print(f"[index] indexed {len(items)} file(s) -> {index_file}")
    return index

def load_index(index_file: Path) -> Dict[str, Any]:
    if not index_file.exists():
        return {"items": []}
    return json.loads(index_file.read_text(encoding="utf-8"))

def search(index: Dict[str, Any], keyword,
           context_chars: int = 80,
           expand: bool = True,
           kinds: set | None = None) -> List[Dict[str, Any]]:
    """Return matches grouped per media file, with surrounding context."""
    if isinstance(keyword, str):
        keywords = [keyword]
    else:
        keywords = list(keyword)
    keywords = [k.strip() for k in keywords if k and k.strip()]
    if not keywords:
        return []

    patterns = []
    for k in keywords:
        if expand:
            try:
                from . import nlp_search
                variants = nlp_search.expand(k)
            except Exception as ex:
                variants = [k]
        else:
            variants = [k]
            
        seen = set()
        deduped = []
        for v in sorted(variants, key=len, reverse=True):
            if v and v not in seen:
                seen.add(v)
                deduped.append(v)
                
        pat = re.compile(
            r"\b(?:" + "|".join(re.escape(v) for v in deduped) + r")\b",
            re.IGNORECASE,
        )
        patterns.append(pat)

    results = []
    for item in index.get("items", []):
        matches = []
        matched_pattern_indices = set()
        
        for seg in item["segments"]:
            seg_kind = seg.get("kind", "speech")
            if kinds is not None and seg_kind not in kinds:
                continue
            text = seg["text"]
            
            for pi, pat in enumerate(patterns):
                for m in pat.finditer(text):
                    matched_pattern_indices.add(pi)
                    lo = max(0, m.start() - context_chars)
                    hi = min(len(text), m.end() + context_chars)
                    snippet = text[lo:hi]
                    match = {
                        "start": seg["start"],
                        "end": seg["end"],
                        "kind": seg_kind,
                        "snippet": snippet,
                        "full": text,
                        "matched": m.group(0),
                    }
                    if seg.get("objects"):
                        match["objects"] = seg["objects"]
                    matches.append(match)
                    
        if len(matched_pattern_indices) == len(patterns):
            matches.sort(key=lambda m: m["start"])
            results.append({
                "media": item["media"],
                "match_count": len(matches),
                "matches": matches,
            })
            
    results.sort(key=lambda r: r["match_count"], reverse=True)
    return results
