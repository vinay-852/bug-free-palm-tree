"""VideoPipeline: orchestrates media -> storyboard -> render -> narration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from .audio import AudioMixer
from .media import MediaFetcher
from .renderer import VideoRenderer
from .storyboard import StoryboardGenerator

PROJECT_DIR = Path(__file__).resolve().parent.parent
REMO_DIR = PROJECT_DIR / "remotion"
OUT_DIR = PROJECT_DIR / "out"
TMP_DIR = PROJECT_DIR / ".tmp"

RESOLUTIONS = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "2160p": (3840, 2160),
}


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "video"


# Filled in when the agent does not supply an emoji for a scene, so a
# panel is never icon-less.
DEFAULT_EMOJIS = ["🎬", "📖", "💡", "⚡", "🚀", "🎯", "🔥", "🌍", "🧠", "🎉"]


class VideoPipeline:
    """One class per task; this class just sequences them.

    create_video(...) with the agent-controllable options:
      1. MediaFetcher   - resolve each scene's media_queries to data URIs
      2. StoryboardGenerator - write story.svg + scenes.json (resolution,
         fps, pacing, theme, camera style, outro text live in scenes.json)
      3. VideoRenderer  - render the storyboard to MP4 (Remotion)
      4. Narrator/AudioMixer - per-scene TTS (voice/speed), pad, concat, mux
    """

    def __init__(
        self,
        remotion_dir: str | Path = REMO_DIR,
        out_dir: str | Path = OUT_DIR,
        tmp_dir: str | Path = TMP_DIR,
    ) -> None:
        self.fetcher = MediaFetcher()
        self.storyboard = StoryboardGenerator()
        self.renderer = VideoRenderer(remotion_dir)
        self.out_dir = Path(out_dir)
        self.tmp_dir = Path(tmp_dir)

    def create_video(
        self,
        topic: str,
        video_title: str,
        scenes: list[dict],
        language: str = "en-IN",
        voice: str = "Pranav",
        speech_speed: float = 1.0,
        scene_seconds: float = 6.0,
        fps: int = 30,
        resolution: str = "1080p",
        theme: str = "dark",
        camera_style: str = "pan",
        outro_text: str = "THE END",
        progress: Callable[[str], None] | None = None,
    ) -> dict:
        """Build the video. Returns a summary dict with 'status' and 'video_path'.

        progress(stage) is called at each phase when provided.
        """
        def emit(stage: str) -> None:
            if progress:
                progress(stage)

        warnings: list[str] = []
        prepared = []
        media_found = 0

        emit("fetching media")
        for scene in scenes:
            entry = {
                "title": scene.get("title", "Scene"),
                "caption": scene.get("caption", ""),
                "emoji": scene.get("emoji") or DEFAULT_EMOJIS[len(prepared) % len(DEFAULT_EMOJIS)],
                "media": [],
            }
            queries = scene.get("media_queries") or []
            types = scene.get("media_types") or []
            for query, mtype in zip(queries, types):
                try:
                    items = self.fetcher.fetch(str(mtype), str(query))
                except Exception as exc:  # noqa: BLE001 - media is best-effort
                    warnings.append(f"media fetch failed for '{query}': {exc}")
                    items = []
                if not items and str(mtype) != "image":
                    # Fall back to a plain image so the panel is not bare.
                    items = self.fetcher.fetch("image", str(query))
                entry["media"].extend(items)
                media_found += len(items)
            prepared.append(entry)

        video_w, video_h = RESOLUTIONS.get(resolution, RESOLUTIONS["1080p"])

        try:
            emit("building storyboard")
            self.storyboard.build(
                video_title,
                prepared,
                REMO_DIR / "public" / "story.svg",
                REMO_DIR / "public" / "scenes.json",
                video_w=video_w,
                video_h=video_h,
                fps=fps,
                scene_seconds=scene_seconds,
                theme=theme,
                camera_style=camera_style,
                outro_text=outro_text,
            )
            emit("rendering video (remotion)")
            self.renderer.render(self.out_dir / "silent.mp4")
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": str(exc), "warnings": warnings}

        final = self.out_dir / f"{_slug(video_title)}.mp4"
        emit("narrating (gnani tts)")
        mixer = AudioMixer(scene_seconds=scene_seconds, tmp_dir=self.tmp_dir)
        narration = mixer.build_narration(scenes, language, voice=voice, speed=speech_speed)
        emit("muxing audio + video")
        try:
            mixer.mux(self.out_dir / "silent.mp4", narration, final)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"mux failed ({exc}); keeping silent video")
            (self.out_dir / "silent.mp4").rename(final)

        return {
            "status": "ok",
            "topic": topic,
            "video_title": video_title,
            "video_path": str(final),
            "scenes": len(prepared),
            "media_embedded": media_found,
            "narration": bool(narration),
            "resolution": f"{video_w}x{video_h}",
            "fps": fps,
            "scene_seconds": scene_seconds,
            "camera_style": camera_style,
            "theme": theme,
            "warnings": warnings,
        }