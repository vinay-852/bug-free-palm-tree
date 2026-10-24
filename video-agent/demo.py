"""Build a demo video WITHOUT an LLM (no API keys needed).

Runs the same pipeline the agent uses: fetch media, build storyboard,
render with Remotion, narrate with Gnani TTS (if GNANI_API_KEY is set).
"""

from video_agent import VideoPipeline

SCENES = [
    {
        "title": "Morning Coffee",
        "caption": "The day starts with caffeine",
        "narration": "Every developer day starts with coffee.",
        "media_queries": ["coffee cup"],
        "media_types": ["image"],
    },
    {
        "title": "Standup",
        "caption": "Yesterday I fixed... wait, no.",
        "narration": "Standup begins, and the story changes halfway.",
        "media_queries": ["office meeting"],
        "media_types": ["image"],
    },
    {
        "title": "Deep Work",
        "caption": "Phone in another room. Really.",
        "narration": "Headphones on. The code is flowing.",
        "media_queries": ["programming code screen"],
        "media_types": ["image"],
    },
    {
        "title": "Debugging",
        "caption": "It's always the off-by-one",
        "narration": "Why is this null? Why is this null.",
        "media_queries": ["debugging"],
        "media_types": ["meme"],
    },
    {
        "title": "Code Review",
        "caption": "LGTM. (Reads the diff anyway.)",
        "narration": "Approved. Ship it.",
        "media_queries": ["github pull request"],
        "media_types": ["image"],
    },
    {
        "title": "Deploy",
        "caption": "6 PM. It goes live.",
        "narration": "Deployed to production. Time for chai.",
        "media_queries": ["rocket launch"],
        "media_types": ["gif"],
    },
]

if __name__ == "__main__":
    import pprint

    pipeline = VideoPipeline()
    summary = pipeline.create_video(
        "a day of a developer",
        "A DAY OF A DEVELOPER",
        SCENES,
        language="en-IN",
        scene_seconds=5,
        fps=30,
        resolution="720p",
        camera_style="zoom",
        theme="dark",
        outro_text="SHIP IT.",
    )
    pprint.pprint(summary)