"""Light NLP layer for the keyword index.

Given a search keyword, returns a list of related forms (lemmas + WordNet
synonyms) so that searching for "shoe" also matches "shoes", "boots",
"sneakers"; "spec" also matches "spectacles", "glasses"; etc.

NLTK is lazy-loaded. If it isn't installed or the WordNet corpus can't be
downloaded, `expand()` falls back to returning just the original keyword.
"""
from __future__ import annotations
from typing import List

_READY = False
_AVAILABLE = False
_WN = None
_LEMMATIZER = None
_CACHE: dict[str, List[str]] = {}

MAX_VARIANTS = 15


def _ensure_loaded() -> bool:
    global _READY, _AVAILABLE, _WN, _LEMMATIZER
    if _READY:
        return _AVAILABLE
    _READY = True
    try:
        import nltk  # type: ignore
        from nltk.corpus import wordnet  # type: ignore
        from nltk.stem import WordNetLemmatizer  # type: ignore
        for pkg in ("wordnet", "omw-1.4"):
            try:
                wordnet.ensure_loaded()
                break
            except LookupError:
                pass
            try:
                nltk.download(pkg, quiet=True)
            except Exception:
                pass
        try:
            wordnet.ensure_loaded()
        except Exception:
            pass
        _WN = wordnet
        _LEMMATIZER = WordNetLemmatizer()
        _AVAILABLE = True
    except Exception as ex:
        print(f"[nlp] WordNet/NLTK unavailable ({ex.__class__.__name__}); "
              "keyword expansion disabled.")
        _AVAILABLE = False
    return _AVAILABLE


def expand(keyword: str) -> List[str]:
    """Return a deduped list of lowercase variants including the original."""
    kw = (keyword or "").strip().lower()
    if not kw:
        return []
    if kw in _CACHE:
        return _CACHE[kw]
    out: List[str] = [kw]
    if _ensure_loaded():
        try:
            lemmas = {kw}
            for pos in ("n", "v", "a", "r"):
                lemmas.add(_LEMMATIZER.lemmatize(kw, pos=pos))
            # Only mine synonyms from synsets whose principal lemma matches the
            # keyword. This avoids slang/alternate-sense pollution such as
            # cat -> guy/hombre/bozo/caterpillar/kat/vomit.
            for lemma in list(lemmas):
                out.append(lemma)
                for syn in _WN.synsets(lemma):
                    primary = syn.lemmas()[0].name().replace("_", " ").lower()
                    if primary != lemma:
                        continue
                    for l in syn.lemmas():
                        name = l.name().replace("_", " ").lower()
                        if " " in name or "-" in name or "'" in name:
                            continue  # single clean token only
                        out.append(name)
                        if len(out) >= MAX_VARIANTS:
                            break
                    if len(out) >= MAX_VARIANTS:
                        break
                if len(out) >= MAX_VARIANTS:
                    break
        except Exception as ex:
            print(f"[nlp] expand({kw!r}) failed: {ex}")
    # dedupe preserving order
    seen = set()
    deduped: List[str] = []
    for w in out:
        if w and w not in seen:
            seen.add(w)
            deduped.append(w)
    _CACHE[kw] = deduped
    return deduped
