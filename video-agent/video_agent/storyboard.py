"""Generate a storyboard SVG + scenes.json for the Remotion renderer.

Panel layout contract (mirrored in remotion/src/StoryVideo.tsx):
  - viewBox: 0 0 (N*1200 + 50) 2160
  - panel i: x = 50 + 1200*i .. 1200*(i+1), y = 760 .. 1400 (center y = 1080)
  - one scene per panel; up to 2 media slots (data URIs) per panel

scenes.json carries the video-level options the Remotion project reads
(resolution, fps, pacing, camera style, theme, outro text), so the agent
controls the whole video, not just the scene text.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from .media import MediaItem

PANEL_STEP = 1200
PANEL_WIDTH = 1150
PANEL_X0 = 50
PANEL_Y = 760
PANEL_HEIGHT = 640
SVG_H = 2160

ACCENTS = ["#22d3ee", "#a78bfa", "#f59e0b", "#f87171", "#34d399", "#f472b6"]

THEMES = {
    "dark": {
        "bg0": "#0b1220",
        "bg1": "#0e1628",
        "card": "#131c2e",
        "border": "#22304e",
        "text": "#e2e8f0",
        "muted": "#94a3b8",
    },
    "light": {
        "bg0": "#f1f5f9",
        "bg1": "#e2e8f0",
        "card": "#ffffff",
        "border": "#cbd5e1",
        "text": "#0f172a",
        "muted": "#64748b",
    },
}


def _esc(text: str) -> str:
    return escape(str(text))


class StoryboardGenerator:
    """Builds the storyboard SVG + scenes.json consumed by Remotion."""

    def __init__(self, scene_seconds: float = 6.0, fps: int = 30, theme: str = "dark") -> None:
        self.scene_seconds = scene_seconds
        self.fps = fps
        self.theme = theme

    def scene_seconds(self) -> float:
        return self.scene_seconds

    def _panel(self, index: int, scene: dict, total: int, palette: dict) -> str:
        accent = ACCENTS[index % len(ACCENTS)]
        x = PANEL_X0 + index * PANEL_STEP
        title = _esc(scene.get("title", f"Scene {index + 1}"))[:48]
        caption = _esc(scene.get("caption", ""))[:110]
        emoji = _esc(scene.get("emoji", ""))[:8]
        media: list[MediaItem] = (scene.get("media") or [])[:2]

        slots = ""
        for j, item in enumerate(media):
            sx = 70 + j * 510
            sy = 250
            cid = f"clip_{index}_{j}"
            slots += f"""
      <clipPath id="{cid}"><rect x="{sx}" y="{sy}" width="500" height="360" rx="24"/></clipPath>
      <image href="{item.uri}" x="{sx}" y="{sy}" width="500" height="360"
             preserveAspectRatio="xMidYMid slice" clip-path="url(#{cid})"/>"""
            if item.meme_caption:
                top, bottom = item.meme_caption
                slots += f"""
      <text x="{sx + 250}" y="{sy + 52}" font-size="40" font-weight="800"
            fill="#ffffff" stroke="#000000" stroke-width="9" paint-order="stroke"
            text-anchor="middle" font-family="Impact, Arial Black, sans-serif">{_esc(top)}</text>
      <text x="{sx + 250}" y="{sy + 336}" font-size="40" font-weight="800"
            fill="#ffffff" stroke="#000000" stroke-width="9" paint-order="stroke"
            text-anchor="middle" font-family="Impact, Arial Black, sans-serif">{_esc(bottom)}</text>"""

        return f"""
  <g transform="translate({x}, {PANEL_Y})">
    <rect width="{PANEL_WIDTH}" height="{PANEL_HEIGHT}" rx="40" fill="{palette['card']}" stroke="{palette['border']}" stroke-width="4"/>
    <text x="60" y="80" font-size="34" font-weight="700" fill="{accent}">SCENE {index + 1}/{total}</text>
    {f'<text x="990" y="165" font-size="110" text-anchor="end">{emoji}</text>' if emoji else ''}
    <text x="60" y="150" font-size="60" font-weight="800" fill="{palette['text']}">{title}</text>
    <text x="60" y="208" font-size="34" fill="{palette['muted']}">{caption}</text>
    {slots}
  </g>"""

    def build(
        self,
        title: str,
        scenes: list[dict],
        svg_path: str | Path,
        json_path: str | Path,
        video_w: int = 1920,
        video_h: int = 1080,
        fps: int | None = None,
        scene_seconds: float | None = None,
        theme: str | None = None,
        camera_style: str = "pan",
        outro_text: str = "THE END",
    ) -> dict:
        """Write story.svg + scenes.json.

        scenes[i] = {title, caption, media: [MediaItem]}.
        Returns the metadata dict written to scenes.json.
        """
        fps = fps or self.fps
        scene_seconds = scene_seconds if scene_seconds is not None else self.scene_seconds
        theme = theme or self.theme
        palette = THEMES.get(theme, THEMES["dark"])

        n = max(1, len(scenes))
        svg_w = n * PANEL_STEP + 50
        panels = "".join(self._panel(i, scenes[i], n, palette) for i in range(n))

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {SVG_H}"
     font-family="system-ui, -apple-system, sans-serif">
  <defs>
    <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{palette['bg0']}"/>
      <stop offset="100%" stop-color="{palette['bg1']}"/>
    </linearGradient>
  </defs>
  <rect width="{svg_w}" height="{SVG_H}" fill="url(#bgGrad)"/>
  {panels}
</svg>"""

        Path(svg_path).write_text(svg)

        meta = {
            "title": title,
            "svg_w": svg_w,
            "svg_h": SVG_H,
            "scene_frames": round(scene_seconds * fps),
            "scene_count": n,
            "fps": fps,
            "video_w": video_w,
            "video_h": video_h,
            "theme": theme,
            "camera_style": camera_style,
            "outro_text": outro_text,
        }
        Path(json_path).write_text(json.dumps(meta))
        return meta