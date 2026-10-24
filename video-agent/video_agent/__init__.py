"""Video generation pipeline: media -> storyboard SVG -> Remotion MP4 -> TTS narration.

Modules (one task each):
    media.py      MediaFetcher  - fetch images/GIFs/memes from free keyless endpoints
    storyboard.py StoryboardGenerator - build story.svg + scenes.json
    renderer.py   VideoRenderer - render the storyboard to MP4 with Remotion
    tts.py        Narrator      - Gnani AI text-to-speech (optional)
    audio.py      AudioMixer    - pad/concat narration and mux it with the video
    pipeline.py   VideoPipeline - orchestrates all of the above
"""

from . import tls as _tls  # noqa: F401 - dev-sandbox TLS patch (see tls.py)

from .media import MediaFetcher, MediaItem
from .storyboard import StoryboardGenerator
from .renderer import VideoRenderer
from .stt import Transcriber
from .tts import Narrator
from .audio import AudioMixer
from .pipeline import VideoPipeline

__all__ = [
    "MediaFetcher",
    "MediaItem",
    "StoryboardGenerator",
    "VideoRenderer",
    "Transcriber",
    "Narrator",
    "AudioMixer",
    "VideoPipeline",
]