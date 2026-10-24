"""ADK tool wiring: expose VideoPipeline as a callable tool for the agent."""

from __future__ import annotations

from google.adk.tools import FunctionTool

from video_agent import Transcriber, VideoPipeline
from video_agent import runtime

_pipeline = VideoPipeline()
_transcriber = Transcriber()


def create_topic_video(
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
) -> str:
    """Create an MP4 short video for a topic.

    Fetches images/GIFs/memes from the internet, builds a storyboard SVG,
    renders it to video with Remotion, and adds a text-to-speech narration.

    Args:
        topic: The subject of the video (used to search for media).
        video_title: The on-screen title of the video.
        scenes: 4-10 scenes (enough for at least a 60-second video).
            Each scene is a dict with:
            - title: short scene headline (<= 40 chars)
            - caption: one supporting line (<= 90 chars)
            - emoji: ONE emoji icon for the scene (optional but encouraged,
              e.g. "☕", "🐛", "🚀")
            - narration: one or two spoken sentences, <= 25 words total,
              in the target language
            - media_queries: 1-2 short English search phrases for media
            - media_types: same length as media_queries; each is
              "image", "gif" or "meme"
        language: Narration language code, e.g. "en-IN", "hi-IN", "te-IN".
        voice: Gnani TTS voice (e.g. "Pranav", "Nalini", "Kaveri", "Deepak").
        speech_speed: Narration speed multiplier, 0.7-1.5 (1.0 = normal).
        scene_seconds: Seconds per scene, 3-15 (the pipeline stretches it
            automatically so the video is at least 60 seconds).
        fps: Frames per second: 24, 30 or 60.
        resolution: "720p", "1080p" or "2160p".
        theme: "dark" or "light" color theme.
        camera_style: "pan" (drift across each panel), "zoom" (slow zoom
            into each panel) or "static" (fixed framing).
        outro_text: Closing text shown at the end (e.g. "SHIP IT.").

    Returns:
        A summary of what was created and the final video path.
    """
    summary = _pipeline.create_video(
        topic=topic,
        video_title=video_title,
        scenes=scenes,
        language=language,
        voice=voice,
        speech_speed=speech_speed,
        scene_seconds=scene_seconds,
        fps=fps,
        resolution=resolution,
        theme=theme,
        camera_style=camera_style,
        outro_text=outro_text,
        progress=runtime.emit,
    )
    runtime.set_last_summary(summary)
    if summary["status"] != "ok":
        return f"Video creation failed: {summary.get('error', 'unknown error')}"

    lines = [
        f"Video created: {summary['video_path']}",
        f"Topic: {summary['topic']}",
        f"Scenes: {summary['scenes']}, media embedded: {summary['media_embedded']}",
        f"Format: {summary['resolution']} @ {summary['fps']}fps, {summary['scene_seconds']}s/scene",
        f"Style: {summary['theme']} theme, {summary['camera_style']} camera",
        f"Narration: {'added via Gnani TTS' if summary['narration'] else 'none (set GNANI_API_KEY)'}",
    ]
    return "\n".join(lines + summary["warnings"])


# ADK 2.x: FunctionTool infers name/description/schema from the function.
create_topic_video_tool = FunctionTool(create_topic_video)


def transcribe_audio(audio_path: str, language_code: str = "en-IN") -> str:
    """Transcribe a voice note or audio file to text using Gnani STT (Prisma).

    Use this when the user gives you an audio file instead of text.
    Audio up to ~60 seconds (REST); longer files are not supported yet.

    Args:
        audio_path: Path to the audio file (wav/mp3/m4a/ogg/aac/flac;
            other formats like webm are converted automatically).
        language_code: BCP-47 code of the speech, e.g. "en-IN", "hi-IN",
            "te-IN", "ta-IN", "kn-IN", "bn-IN".

    Returns:
        The transcript text, or an error message if transcription failed.
    """
    try:
        return _transcriber.transcribe(audio_path, language_code)
    except Exception as exc:  # noqa: BLE001 - surface the error to the agent
        return f"Transcription failed: {exc}"


transcribe_audio_tool = FunctionTool(transcribe_audio)