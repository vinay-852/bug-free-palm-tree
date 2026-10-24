"""ADK agent: Gemini plans the video, tools build it.

Run:
    export GEMINI_API_KEY=...
    export GNANI_API_KEY=...            # optional; without it the video is silent
    python agent.py "why the sky is blue"
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from tools import create_topic_video_tool, transcribe_audio_tool

load_dotenv()

INSTRUCTION = """You are a short-video creator for Indian audiences.
A user gives you a topic (as text or as a voice note). You plan a 3-6
scene video story and build it.

INPUT: if the user's message is a path to an audio file (voice note),
FIRST call transcribe_audio to turn it into text, then plan and build
the video from that text. If the message is plain text, skip
transcription and go straight to planning.

Rules for your plan:
- scenes: 6 to 10 (the video must be at least 60 seconds long).
- Each scene has: title (<=40 chars), caption (<=90 chars),
  emoji (ONE emoji icon for the panel, e.g. "☕" "🐛" "🚀" — always add one),
  narration (one or two spoken sentences, <=25 words total, in the
  requested language), media_queries (1-2 short English phrases to search
  for images/gifs), media_types matching the queries
  ("image", "gif" or "meme").
- Mix media: use "image" for photos, "gif" for animated clips, "meme" for
  funny meme templates (use sparingly, one per video is enough).
- video_title: short and punchy, shown on screen.
- language: DETECT the language the user writes in and use its code for
  the narration language (Telugu -> "te-IN", Hindi -> "hi-IN", Tamil ->
  "ta-IN", Kannada -> "kn-IN", Bengali -> "bn-IN", default "en-IN").
  On-screen titles/captions may stay in English unless the user asks
  otherwise.
- Keep narration spoken-style (it is read aloud by a text-to-speech voice).

You also control the video style - pick sensible values for the topic and
the user's request:
- resolution: "720p", "1080p" (default) or "2160p"
- fps: 24, 30 (default) or 60
- scene_seconds: 6-12 seconds per scene; pick so that
  scene_count * scene_seconds >= 60 (at least a 1-minute video)
- camera_style: "pan" (default), "zoom" (cinematic) or "static"
- theme: "dark" (default) or "light"
- voice: a Gnani TTS voice, e.g. "Pranav", "Nalini", "Kaveri", "Deepak"
- speech_speed: 0.9-1.1 for a natural pace
- outro_text: a short closing line (e.g. "SHIP IT.", "STAY CURIOUS.")

Then call create_topic_video with the complete plan. Report the result
to the user, including the path to the MP4.
"""

video_agent = LlmAgent(
    name="video_maker",
    model="gemini-3.8-flash",
    instruction=INSTRUCTION,
    tools=[create_topic_video_tool, transcribe_audio_tool],
)


def run_agent(message: str) -> str:
    """Run the ADK agent on a message and return its final text.

    The agent has full control: it may call transcribe_audio and
    create_topic_video (whose last summary is stored in
    video_agent.runtime for the caller to pick up).
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return "Set GEMINI_API_KEY first."
    session_service = InMemorySessionService()
    session_service.create_session_sync(
        app_name="video_maker_app", user_id="local", session_id="default"
    )
    runner = Runner(
        agent=video_agent,
        app_name="video_maker_app",
        session_service=session_service,
    )
    content = genai_types.Content(role="user", parts=[genai_types.Part(text=message)])
    for event in runner.run(user_id="local", session_id="default", new_message=content):
        if event.is_final_response() and event.content:
            parts = event.content.parts
            return "".join(p.text or "" for p in parts) if parts else str(event.content)
    return "No response"


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) or "why the sky is blue"
    print(run_agent(topic))