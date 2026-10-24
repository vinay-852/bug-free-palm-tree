"""Render the storyboard SVG to an MP4 with Remotion (headless)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


class VideoRenderer:
    """Runs `npx remotion render` against the bundled Remotion project.

    The project reads public/story.svg + public/scenes.json at bundle
    time; --bundle-cache=false forces a fresh bundle every render so a
    new storyboard always produces a new video.
    """

    def __init__(self, remotion_dir: str | Path | None = None, timeout: int = 600) -> None:
        self.remotion_dir = Path(remotion_dir or PROJECT_DIR / "remotion")
        self.timeout = timeout

    def render(self, output_path: str | Path) -> Path:
        """Render the current storyboard to `output_path` (an MP4)."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        proc = subprocess.run(
            [
                "npx",
                "remotion",
                "render",
                "src/index.ts",
                "StoryVideo",
                "out/story.mp4",
                "--bundle-cache=false",
            ],
            cwd=str(self.remotion_dir),
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"remotion render failed ({proc.returncode}): "
                f"{(proc.stdout or '')[-400:]} {(proc.stderr or '')[-400:]}"
            )

        rendered = self.remotion_dir / "out" / "story.mp4"
        if not rendered.exists():
            raise RuntimeError("remotion render finished but produced no output file")
        shutil.copy(rendered, output_path)
        return output_path