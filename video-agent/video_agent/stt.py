"""Gnani AI (vachana) speech-to-text wrapper (Prisma).

Optional: needs GNANI_API_KEY. The REST STT is limited to ~60s of audio;
longer inputs should use the batch API (not implemented here).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .runtime import dry_run

SUPPORTED_EXT = {".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a"}


class Transcriber:
    """Transcribes voice notes / audio files via Gnani Prisma (REST)."""

    def __init__(self, tmp_dir: str | Path | None = None) -> None:
        self.tmp_dir = Path(tmp_dir) if tmp_dir else Path(__file__).resolve().parent.parent / ".tmp"

    def available(self) -> bool:
        return bool(os.environ.get("GNANI_API_KEY"))

    def _normalize(self, audio: str | Path) -> Path:
        """Convert unsupported formats (e.g. webm) to 16 kHz mono WAV and
        trim anything longer than the STT REST limit (~60s)."""
        path = Path(audio)
        needs_convert = path.suffix.lower() not in SUPPORTED_EXT
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        out = self.tmp_dir / f"{path.stem}_stt.wav"
        if needs_convert:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(path), "-ar", "16000", "-ac", "1", str(out)],
                check=True,
                capture_output=True,
            )
            path = out

        # Keep only the first 58s (the REST endpoint caps around 60s).
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True,
            text=True,
        )
        try:
            duration = float(probe.stdout.strip())
        except ValueError:
            duration = 0.0
        if duration > 58:
            trimmed = self.tmp_dir / f"{path.stem}_trim.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(path), "-t", "58",
                 "-ar", "16000", "-ac", "1", str(trimmed)],
                check=True,
                capture_output=True,
            )
            return trimmed
        return path

    def transcribe(self, audio: str | Path, language_code: str = "en-IN") -> str:
        """Transcribe an audio file and return the transcript text.

        In dry-run mode returns a canned transcript without calling Gnani.
        """
        if dry_run():
            return (
                f"Mock transcript ({language_code}): this voice note asks how "
                f"the internet works. Please make a short video about it."
            )
        if not self.available():
            raise RuntimeError("GNANI_API_KEY not set - cannot transcribe")
        from gnani.stt import GnaniSTTClient

        client = GnaniSTTClient()
        result = client.transcribe(
            self._normalize(audio),
            language_code=language_code,
            format="verbatim",
        )
        return result.get("transcript", "")