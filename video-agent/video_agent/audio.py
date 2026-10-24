"""Assemble narration audio and mux it with the rendered video (ffmpeg)."""

from __future__ import annotations

import subprocess
from pathlib import Path


class AudioMixer:
    """Per-scene narration -> one track -> muxed with the video.

    Each scene's narration is padded to exactly one scene duration, the
    padded clips are concatenated, and the result is muxed into the
    video as an AAC track.
    """

    def __init__(self, scene_seconds: float, tmp_dir: str | Path) -> None:
        self.scene_seconds = scene_seconds
        self.tmp_dir = Path(tmp_dir)

    def build_narration(
        self,
        scenes: list[dict],
        language: str,
        voice: str = "Pranav",
        speed: float = 1.0,
    ) -> Path | None:
        """One TTS call per scene, padded to scene length, concatenated.

        Returns the narration WAV path, or None when there is no audio.
        """
        from .tts import Narrator

        narrator = Narrator(voice=voice, speed=speed)
        if not narrator.available():
            return None

        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        padded: list[Path] = []
        for i, scene in enumerate(scenes):
            text = (scene.get("narration") or "").strip()
            if not text:
                continue
            raw = self.tmp_dir / f"n_{i}.wav"
            if not narrator.synthesize(text, language, raw):
                continue
            pad = self.tmp_dir / f"n_{i}_pad.wav"
            cmd = [
                "ffmpeg", "-y", "-v", "error", "-i", str(raw),
                "-af", f"apad=pad_dur={self.scene_seconds},atrim=0:{self.scene_seconds}",
                "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(pad),
            ]
            if subprocess.run(cmd, capture_output=True).returncode == 0:
                padded.append(pad)

        if not padded:
            return None

        list_file = self.tmp_dir / "concat.txt"
        list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in padded))
        full = self.tmp_dir / "narration.wav"
        code = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                "-i", str(list_file), "-c", "copy", str(full),
            ],
            capture_output=True,
        ).returncode
        return full if code == 0 else None

    def mux(self, video: str | Path, narration: str | Path | None, final: str | Path) -> None:
        """Mux narration (or silence) into the video, producing `final`."""
        final = Path(final)
        final.parent.mkdir(parents=True, exist_ok=True)
        if narration and Path(narration).exists():
            cmd = [
                "ffmpeg", "-y", "-v", "error",
                "-i", str(video), "-i", str(narration),
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(final),
            ]
        else:
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-c", "copy", str(final)]
        subprocess.run(cmd, capture_output=True, check=True)