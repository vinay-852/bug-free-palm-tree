"""Gnani AI (vachana) text-to-speech wrapper.

Optional: if GNANI_API_KEY is not set, narration is skipped and the
video is produced silent.
"""

from __future__ import annotations

import os

MODEL = "timbre-v2.5"


class Narrator:
    """Synthesizes narration audio via the Gnani TTS REST API."""

    def __init__(
        self,
        voice: str | None = None,
        model: str = MODEL,
        speed: float = 1.0,
    ) -> None:
        self.voice = voice or os.environ.get("GNANI_VOICE", "Pranav")
        self.model = model
        self.speed = speed

    def available(self) -> bool:
        return bool(os.environ.get("GNANI_API_KEY"))

    def synthesize(self, text: str, language: str, out_path: str | os.PathLike) -> bool:
        """Synthesize text to a WAV file. Returns False when skipped/failed."""
        if not self.available():
            return False
        try:
            from gnani.tts import GnaniTTSClient

            client = GnaniTTSClient()  # reads GNANI_API_KEY
            try:
                client.synthesize(
                    text[:400],
                    voice=self.voice,
                    model=self.model,
                    language=language,
                    speed=self.speed,
                    output_file=str(out_path),
                )
            except TypeError:
                # Older SDK builds do not accept `speed`; retry without it.
                client.synthesize(
                    text[:400],
                    voice=self.voice,
                    model=self.model,
                    language=language,
                    output_file=str(out_path),
                )
            return True
        except Exception as exc:  # noqa: BLE001 - TTS is best-effort
            print(f"[tts] skipped '{text[:40]}...': {exc}")
            return False