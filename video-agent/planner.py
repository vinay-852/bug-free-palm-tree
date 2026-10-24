"""Plan a video: topic + language -> scene list (with options).

Uses Gemini for creative planning (JSON mode), falling back to a
deterministic heuristic planner when no GEMINI_API_KEY is set or the
call fails, so the web UI works out of the box.
"""

from __future__ import annotations

import json
import math
import os
import re

LANGUAGES = {
    "en-IN": "English",
    "hi-IN": "Hindi",
    "te-IN": "Telugu",
    "ta-IN": "Tamil",
    "kn-IN": "Kannada",
    "bn-IN": "Bengali",
    "mr-IN": "Marathi",
    "gu-IN": "Gujarati",
}

MODEL = os.environ.get("PLANNER_MODEL", "gemini-3.8-flash")

LANGUAGE_HINTS = {
    "te-IN": ("తెలుగు", "telugu"),
    "hi-IN": ("हिंदी", "hindi"),
    "ta-IN": ("தமிழ்", "tamil"),
    "kn-IN": ("ಕನ್ನಡ", "kannada"),
    "bn-IN": ("বাংলা", "bengali"),
    "mr-IN": ("मराठी", "marathi"),
    "gu-IN": ("ગુજરાતી", "gujarati"),
}


def _infer_language(text: str) -> str:
    for code, (script_hint, name_hint) in LANGUAGE_HINTS.items():
        if script_hint in text or name_hint in text.lower():
            return code
    script_ranges = {
        "te-IN": (0x0C00, 0x0C7F),
        "hi-IN": (0x0900, 0x097F),
        "ta-IN": (0x0B80, 0x0BFF),
        "kn-IN": (0x0C80, 0x0CFF),
        "bn-IN": (0x0980, 0x09FF),
        "mr-IN": (0x0900, 0x097F),
        "gu-IN": (0x0A80, 0x0AFF),
    }
    for char in text:
        point = ord(char)
        for code, (start, end) in script_ranges.items():
            if start <= point <= end:
                return code
    return "en-IN"


PLAN_PROMPT = """You are a short-video planner. Plan a 6-10 scene video for the
topic below (enough for at least a 1-minute video).
Return ONLY a JSON object with this exact shape:
{{
  "title": "short punchy on-screen title",
  "language": "BCP-47 narration language code",
  "scenes": [
    {{
      "title": "scene headline (<=40 chars)",
      "caption": "one supporting line (<=90 chars)",
      "emoji": "one emoji icon for the scene",
      "narration": "one or two spoken sentences, <=25 words total, in the narration language",
      "media_queries": ["1-2 short English search phrases"],
      "media_types": ["image|gif|meme for each query"]
    }}
  ],
  "options": {{
    "resolution": "720p|1080p|2160p",
    "fps": 30,
    "scene_seconds": 8,
    "camera_style": "pan|zoom|static",
    "theme": "dark|light",
    "outro_text": "short closing line",
    "voice": "Pranav",
    "speech_speed": 1.0
  }}
}}
Rules: 6-10 scenes; first sets context, last wraps up; mix "image"/"gif"/
"meme" (one meme per video max); narration is spoken-style and in the
requested language; keep emoji in every scene. Choose scene_seconds so
scenes * scene_seconds >= 60.

Topic: {topic}
Requested language: {language_name} ({language_code})
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


def _plan_with_gemini(topic: str, language_code: str) -> dict | None:
    if os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes"):
        return None  # dry run: skip Gemini entirely
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client()
        language_name = LANGUAGES.get(language_code, language_code)
        response = client.models.generate_content(
            model=MODEL,
            contents=PLAN_PROMPT.format(
                topic=topic, language_name=language_name, language_code=language_code
            ),
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        plan = _extract_json(response.text)
        if not plan.get("scenes"):
            return None
        return plan
    except Exception as exc:  # noqa: BLE001 - fall back to heuristic
        print(f"[planner] gemini planning failed ({exc}); using heuristic")
        return None


def _plan_heuristic(topic: str, language_code: str) -> dict:
    """Deterministic fallback so the UI works without a Gemini key."""
    short = topic[:40]
    narrations = {
        "en-IN": [
            "Here is the story of this topic, told quickly.",
            "It starts with a simple idea.",
            "The details matter more than you think.",
            "Here is a fun way to look at it.",
            "People ask about this all the time.",
            "That is the short version. Stay curious.",
        ],
    }
    lines = narrations.get(language_code, narrations["en-IN"])
    scenes = [
        {
            "title": short,
            "caption": "The topic, in under a minute",
            "emoji": "🎬",
            "narration": lines[0],
            "media_queries": [topic],
            "media_types": ["image"],
        },
        {
            "title": "How It Starts",
            "caption": "A simple idea",
            "emoji": "💡",
            "narration": lines[1],
            "media_queries": [f"{topic} concept"],
            "media_types": ["image"],
        },
        {
            "title": "Why It Matters",
            "caption": "A closer look",
            "emoji": "�",
            "narration": lines[2],
            "media_queries": [f"{topic} explanation"],
            "media_types": ["image"],
        },
        {
            "title": "Fun Fact",
            "caption": "The meme never lies",
            "emoji": "😂",
            "narration": lines[3],
            "media_queries": ["funny"],
            "media_types": ["meme"],
        },
        {
            "title": "Common Questions",
            "caption": "What everyone asks",
            "emoji": "❓",
            "narration": lines[4],
            "media_queries": [f"{topic} interesting"],
            "media_types": ["image"],
        },
        {
            "title": "Wrap Up",
            "caption": "Now you know",
            "emoji": "🚀",
            "narration": lines[5],
            "media_queries": [topic],
            "media_types": ["gif"],
        },
    ]
    return {
        "title": short.upper(),
        "language": language_code,
        "scenes": scenes,
        "options": {
            "resolution": "1080p",
            "fps": 30,
            "scene_seconds": 10,
            "camera_style": "pan",
            "theme": "dark",
            "outro_text": "THE END",
            "voice": "Pranav",
            "speech_speed": 1.0,
        },
    }


def plan_video(topic: str, language_code: str = "auto") -> dict:
    """Return {title, language, scenes, options} for a topic.

    language_code "auto" lets Gemini detect the narration language from
    the topic text (falls back to en-IN when unavailable).
    Ensures the planned length is at least 60 seconds.
    """
    requested = language_code if language_code in LANGUAGES else _infer_language(topic)
    plan = _plan_with_gemini(topic, requested) or _plan_heuristic(topic, requested)
    plan.setdefault("options", {})
    plan["language"] = plan.get("language") or requested
    n = max(len(plan["scenes"]), 1)
    opts = plan["options"]
    opts["scene_seconds"] = max(
        float(opts.get("scene_seconds", 8)), min(15.0, math.ceil(60.0 / n))
    )
    return plan