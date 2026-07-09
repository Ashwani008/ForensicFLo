"""Extract a mono 16kHz WAV from any media file using ffmpeg.

Resolves ffmpeg.exe even when it's not on PATH (e.g. winget-installed
package whose PATH update hasn't been picked up by the running shell yet).
"""
from __future__ import annotations
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


def _find_ffmpeg() -> str:
    env = os.environ.get("FFMPEG_BINARY")
    if env and Path(env).is_file():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    # Linux/macOS no-root fallback: use bundled binary from imageio-ffmpeg.
    try:
        import imageio_ffmpeg  # type: ignore
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).is_file():
            return bundled
    except Exception:
        pass
    candidates: list[Path] = []
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        pkg_root = Path(local) / "Microsoft" / "WinGet" / "Packages"
        if pkg_root.is_dir():
            candidates.extend(pkg_root.glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe"))
        candidates.append(Path(local) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe")
    candidates.extend([
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
    ])
    for c in candidates:
        if c and Path(c).is_file():
            return str(c)
    raise FileNotFoundError(
        "ffmpeg not found. Install system ffmpeg, or install imageio-ffmpeg, "
        "or set FFMPEG_BINARY to a valid ffmpeg binary path."
    )


_FFMPEG: str | None = None


def get_ffmpeg() -> str:
    """Return path to ffmpeg.exe; also prepends its dir to PATH so libraries
    that shell out to bare 'ffmpeg' (e.g. whisper) find it."""
    global _FFMPEG
    if _FFMPEG is None:
        _FFMPEG = _find_ffmpeg()
        bin_dir = str(Path(_FFMPEG).parent)
        if bin_dir not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    return _FFMPEG


def _has_audio_stream(media_path: Path, ffmpeg_path: str) -> bool:
    """Return True if the media file contains at least one audio stream."""
    ffprobe = Path(ffmpeg_path).with_name("ffprobe.exe")
    if not ffprobe.is_file():
        ffprobe = Path(ffmpeg_path).with_name("ffprobe")
    if not Path(ffprobe).is_file():
        # Fall back to ffmpeg -i stderr parsing
        result = subprocess.run(
            [ffmpeg_path, "-i", str(media_path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        return "Audio:" in result.stderr
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0",
         str(media_path)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    return bool(result.stdout.strip())


def _write_silent_wav(path: Path, sample_rate: int = 16000) -> None:
    """Write a minimal 1-second silent mono WAV file."""
    num_samples = sample_rate
    data_size = num_samples * 2  # 16-bit mono
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))
        f.write(struct.pack("<H", 1))            # PCM
        f.write(struct.pack("<H", 1))            # mono
        f.write(struct.pack("<I", sample_rate))  # sample rate
        f.write(struct.pack("<I", sample_rate * 2))  # byte rate
        f.write(struct.pack("<H", 2))            # block align
        f.write(struct.pack("<H", 16))           # bits per sample
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)


def extract_audio(media_path: Path, sample_rate: int = 16000) -> Path:
    """Return path to a temp mono WAV at the requested sample rate.

    If the media file has no audio stream, returns a silent WAV so that
    downstream transcription/sound-event stages complete without error.
    """
    ffmpeg = get_ffmpeg()
    tmp = Path(tempfile.mkstemp(suffix=".wav")[1])

    if not _has_audio_stream(media_path, ffmpeg):
        print(f"[audio] {media_path.name}: no audio stream — using silent WAV")
        _write_silent_wav(tmp, sample_rate)
        return tmp

    cmd = [
        ffmpeg, "-y", "-i", str(media_path),
        "-ac", "1", "-ar", str(sample_rate),
        "-vn", "-f", "wav", str(tmp),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return tmp
