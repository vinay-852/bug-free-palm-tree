# Video Agent

ADK agent (Gemini) that plans a short video for a topic, pulls images /
GIFs / memes from free keyless endpoints, renders the storyboard to an
MP4 with Remotion, and narrates it with Gnani AI text-to-speech.

## Modular structure (one task per module, classes everywhere)

```
video-agent/
  video_agent/            # Python package
    media.py              # MediaFetcher  - images/GIFs/memes (Openverse, Wikimedia, ImgFlip - keyless)
    storyboard.py         # StoryboardGenerator - story.svg + scenes.json
    renderer.py           # VideoRenderer - Remotion render to MP4
    tts.py                # Narrator      - Gnani TTS (optional; needs GNANI_API_KEY)
    audio.py              # AudioMixer    - pad/concat narration, ffmpeg mux
    pipeline.py           # VideoPipeline - orchestrates the five classes above
  tools.py                # create_topic_video ADK FunctionTool (wraps VideoPipeline)
  agent.py                # ADK LlmAgent (Gemini) that plans scenes and calls the tool
  demo.py                 # keyless end-to-end demo (no LLM needed)
  remotion/               # Remotion renderer project (reads public/story.svg + scenes.json)
```

`VideoPipeline.create_video(topic, title, scenes, language)` sequences:
1. **MediaFetcher** - resolve each scene's `media_queries`/`media_types` to data URIs
2. **StoryboardGenerator** - write `remotion/public/story.svg` + `scenes.json`
3. **VideoRenderer** - `npx remotion render ... --bundle-cache=false`
4. **Narrator + AudioMixer** - per-scene TTS, pad to scene length, concat, mux

Scene schema (used by the agent and `demo.py`):
```python
{
    "title": "<= 40 chars",
    "caption": "<= 90 chars",
    "narration": "one spoken sentence, <= 14 words",
    "media_queries": ["coffee cup"],   # short English search phrases
    "media_types": ["image"],          # "image" | "gif" | "meme"
}
```

Video options the agent controls (all optional, defaults shown):
```python
create_topic_video(
    topic, video_title, scenes, language="en-IN",
    voice="Pranav",          # Gnani TTS voice (Pranav/Nalini/Kaveri/Deepak)
    speech_speed=1.0,        # 0.7-1.5 narration speed
    scene_seconds=6.0,       # pacing: 3-10 s per scene
    fps=30,                  # 24 / 30 / 60
    resolution="1080p",      # "720p" | "1080p" | "2160p"
    theme="dark",            # "dark" | "light"
    camera_style="pan",      # "pan" | "zoom" | "static"
    outro_text="THE END",    # closing line, e.g. "SHIP IT."
)
```
The options are written into `scenes.json`; the Remotion composition reads
them, so resolution/fps/pacing/camera/theme/outro all change per render.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd remotion && npm ci && cd ..

# 1) Demo without an LLM (no API keys):
.venv/bin/python demo.py            # -> out/a-day-of-a-developer.mp4

# 2) With the Gemini agent (text or a voice note):
cp .env.example .env                # add GEMINI_API_KEY (+ GNANI_API_KEY)
.venv/bin/python agent.py "why the sky is blue"
.venv/bin/python agent.py "transcribe .tmp/voice.wav (Telugu, te-IN) and make a video"

# 3) Web UI (text OR audio in -> video out):
.venv/bin/uvicorn web:app --port 8000
# open http://localhost:8000
```

- `GEMINI_API_KEY` - required for the agent (Gemini plans the scenes)
- `GNANI_API_KEY` / `GNANI_VOICE` - optional; without them the video is silent
- Media endpoints need no keys: Openverse, Wikimedia Commons, ImgFlip

## Deploy on Render

1. Push this folder to GitHub (it is ~370 KB — everything regenerable is
   git/docker-ignored; **never commit `.env`**, it holds your API keys).
2. Create a Render web service with `runtime: docker` (render.yaml
   included) or: New -> Web Service -> repo -> Runtime: Docker.
3. Set env vars in the Render dashboard: `GEMINI_API_KEY`,
   `GNANI_API_KEY`, optional `GNANI_VOICE`.
4. Deploy. The Docker image pre-downloads Chrome Headless Shell and
   `npm ci`-s the Remotion project during build, so the first request
   renders immediately.

Notes:
- Renders are CPU-heavy; use at least the `starter` (512 MB) plan, 1 GB
  for 1080p, and prefer 720p for free-tier testing.
- Jobs run in-process with a global lock (single instance) — the UI
  polls `/api/jobs/{id}` until the video is ready.
- The TLS workaround in `video_agent/tls.py` only activates when the
  Python build's certificate verification is broken (macOS python.org
  builds); on the Debian image nothing is patched.

## Notes

- Media is embedded as base64 data URIs, so `story.svg` is self-contained;
  edit it and re-render to change the video (it is a webpack module, so the
  bundle cache invalidates automatically).
- Narration is per-scene, padded to exactly one scene and muxed as AAC;
  longer narration is trimmed. Input audio (voice notes) is transcribed
  with Gnani STT (Prisma) and narrated with Gnani TTS (Timbre).