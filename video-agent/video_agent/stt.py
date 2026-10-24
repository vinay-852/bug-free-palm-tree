"""Gnani AI (vachana) speech-to-text wrapper (Prisma).

Optional: needs GNANI_API_KEY. The REST STT is limited to ~60s of audio;
longer inputs should use the batch API (not implemented here).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

SUPPORTED_EXT = {".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a"}


class Transcriber:
    """Transcribes voice notes / audio files via Gnani Prisma (REST)."""

    def __init__(self, tmp_dir: str | Path | None = None) -> None:
        self.tmp_dir = Path(tmp_dir) if tmp_dir else Path(__file__).resolve().parent.parent / ".tmp"

    def available(self) -> bool:
        return bool(os.environ.get("GNANI_API_KEY"))

    def _normalize(self, audio: str | Path) -> Path:
        """Convert unsupported formats (e.g. webm) to 16 kHz mono WAV."""
        path = Path(audio)
        if path.suffix.lower() in SUPPORTED_EXT:
            return path
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        out = self.tmp_dir / f"{path.stem}_stt.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(path), "-ar", "16000", "-ac", "1", str(out)],
            check=True,
            capture_output=True,
        )
        return out

    def transcribe(self, audio: str | Path, language_code: str = "en-IN") -> str:
        """Transcribe an audio file and return the transcript text."""
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