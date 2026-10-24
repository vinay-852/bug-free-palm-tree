"""FastAPI web UI: text OR audio in, video out.

Run locally:  uvicorn web:app --reload
Deploy:       see render.yaml (Docker runtime)
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

load_dotenv(".env")

from planner import plan_video  # noqa: E402
from video_agent import Transcriber, VideoPipeline  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent
OUT_DIR = PROJECT_DIR / "out"
UPLOAD_DIR = PROJECT_DIR / ".tmp"

app = FastAPI(title="Video Agent")
pipeline = VideoPipeline()
transcriber = Transcriber(tmp_dir=UPLOAD_DIR)

# In-memory job store. Renders are serialized with a global lock because
# the Remotion project writes to a shared public/ directory.
# ponytail: single-instance demo; scale-out needs per-job remotion dirs.
jobs: dict[str, dict] = {}
render_lock = threading.Lock()

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Video Agent</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: system-ui, sans-serif; background:#0b1220; color:#e2e8f0;
         margin:0; min-height:100vh; display:flex; justify-content:center; }
  .card { max-width:680px; width:100%; padding:40px 24px; }
  h1 { letter-spacing:1px; }
  .sub { color:#94a3b8; margin-top:-8px; }
  label { display:block; margin:18px 0 6px; font-weight:600; color:#cbd5e1; }
  input[type=text], textarea, select {
    width:100%; box-sizing:border-box; padding:12px; border-radius:10px;
    border:1px solid #22304e; background:#131c2e; color:#e2e8f0; font-size:15px;
  }
  textarea { min-height:90px; resize:vertical; }
  .row { display:flex; gap:12px; }
  .row > div { flex:1; }
  .tabs { display:flex; gap:8px; margin-top:6px; }
  .tab { flex:1; padding:12px; text-align:center; border-radius:10px; cursor:pointer;
         border:1px solid #22304e; background:#131c2e; color:#94a3b8; font-weight:600; }
  .tab.active { background:#22d3ee; color:#0b1220; border-color:#22d3ee; }
  .panel { display:none; }
  .panel.active { display:block; }
  button { width:100%; padding:14px; margin-top:22px; border:0; border-radius:10px;
           background:#22d3ee; color:#0b1220; font-size:16px; font-weight:800; cursor:pointer; }
  button:disabled { opacity:.5; cursor:wait; }
  #status { margin-top:18px; color:#94a3b8; font-size:14px; white-space:pre-line; }
  #result { margin-top:18px; }
  video { width:100%; border-radius:12px; background:#000; }
  .err { color:#f87171; font-weight:600; }
  .hint { color:#64748b; font-size:13px; margin-top:4px; }
</style>
</head>
<body>
<div class="card">
  <h1>Video Agent</h1>
  <p class="sub">Give it a topic (text or a voice note) and get a narrated video.</p>

  <label>Input</label>
  <div class="tabs">
    <div class="tab active" id="tab-text" onclick="switchTab('text')">Text</div>
    <div class="tab" id="tab-audio" onclick="switchTab('audio')">Audio / Voice note</div>
  </div>

  <div class="panel active" id="panel-text">
    <textarea id="topic" placeholder="e.g. How the internet works, in Telugu..."></textarea>
  </div>
  <div class="panel" id="panel-audio">
    <input type="file" id="audio" accept="audio/*">
    <p class="hint">wav, mp3, m4a, ogg, aac, flac (webm converted automatically). Up to ~60s.</p>
  </div>

  <div class="row">
    <div>
      <label>Language</label>
      <select id="language">
        <option value="auto">Auto (detect)</option>
        <option value="en-IN">English</option>
        <option value="hi-IN">Hindi</option>
        <option value="te-IN">Telugu</option>
        <option value="ta-IN">Tamil</option>
        <option value="kn-IN">Kannada</option>
        <option value="bn-IN">Bengali</option>
        <option value="mr-IN">Marathi</option>
        <option value="gu-IN">Gujarati</option>
      </select>
    </div>
    <div>
      <label>Resolution</label>
      <select id="resolution">
        <option value="720p">720p (fast)</option>
        <option value="1080p" selected>1080p</option>
        <option value="2160p">2160p (slow)</option>
      </select>
    </div>
  </div>
  <div class="row">
    <div>
      <label>Camera</label>
      <select id="camera">
        <option value="pan" selected>Pan</option>
        <option value="zoom">Zoom</option>
        <option value="static">Static</option>
      </select>
    </div>
    <div>
      <label>Theme</label>
      <select id="theme">
        <option value="dark" selected>Dark</option>
        <option value="light">Light</option>
      </select>
    </div>
  </div>
  <div class="row">
    <div>
      <label>Seconds / scene</label>
      <select id="seconds">
        <option value="4">4</option>
        <option value="5" selected>5</option>
        <option value="6">6</option>
        <option value="8">8</option>
      </select>
    </div>
    <div>
      <label>Outro text</label>
      <input type="text" id="outro" value="THE END" maxlength="30">
    </div>
  </div>

  <button id="go" onclick="generate()">Generate video</button>
  <div id="status"></div>
  <div id="result"></div>
</div>

<script>
function switchTab(which) {
  document.getElementById('tab-text').classList.toggle('active', which==='text');
  document.getElementById('tab-audio').classList.toggle('active', which==='audio');
  document.getElementById('panel-text').classList.toggle('active', which==='text');
  document.getElementById('panel-audio').classList.toggle('active', which==='audio');
}
async function generate() {
  const go = document.getElementById('go');
  go.disabled = true;
  const status = document.getElementById('status');
  const result = document.getElementById('result');
  status.textContent = ''; result.innerHTML = '';

  const mode = document.getElementById('panel-text').classList.contains('active') ? 'text' : 'audio';
  const form = new FormData();
  if (mode === 'text') {
    const topic = document.getElementById('topic').value.trim();
    if (!topic) { alert('Enter a topic'); go.disabled = false; return; }
    form.append('text', topic);
  } else {
    const file = document.getElementById('audio').files[0];
    if (!file) { alert('Choose an audio file'); go.disabled = false; return; }
    form.append('audio', file);
  }
  form.append('language', document.getElementById('language').value);
  form.append('resolution', document.getElementById('resolution').value);
  form.append('camera', document.getElementById('camera').value);
  form.append('theme', document.getElementById('theme').value);
  form.append('seconds', document.getElementById('seconds').value);
  form.append('outro', document.getElementById('outro').value || 'THE END');

  let resp = await fetch('/api/generate', {method:'POST', body: form});
  if (!resp.ok) { status.textContent = 'Request failed'; go.disabled = false; return; }
  const {job_id} = await resp.json();

  const poll = setInterval(async () => {
    const r = await fetch('/api/jobs/' + job_id);
    const job = await r.json();
    status.textContent = (job.state === 'running' ? 'Working: ' : '') + job.stage;
    if (job.state === 'done') {
      clearInterval(poll);
      go.disabled = false;
      status.textContent = 'Done';
      result.innerHTML = '<video controls autoplay src="' + job.video_url + '"></video>';
    } else if (job.state === 'error') {
      clearInterval(poll);
      go.disabled = false;
      status.innerHTML = '<span class="err">Failed: ' + job.error + '</span>';
    }
  }, 2000);
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


def _run_job(job_id: str, text: str | None, audio_path: Path | None,
             language: str, options: dict) -> None:
    def emit(stage: str) -> None:
        jobs[job_id]["stage"] = stage

    try:
        jobs[job_id]["state"] = "running"
        jobs[job_id]["stage"] = "transcribing audio" if audio_path else "planning scenes"

        if audio_path is not None:
            stt_lang = language if language != "auto" else "en-IN"
            text = transcriber.transcribe(audio_path, stt_lang)
            if not text:
                raise RuntimeError("Speech-to-text returned an empty transcript")

        plan = plan_video(text or "", language)
        scenes = plan["scenes"]
        opts = {**plan.get("options", {}), **options}

        with render_lock:
            summary = pipeline.create_video(
                topic=text or "",
                video_title=plan["title"],
                scenes=scenes,
                language=plan["language"],
                voice=opts.get("voice", "Pranav"),
                speech_speed=float(opts.get("speech_speed", 1.0)),
                scene_seconds=float(opts.get("scene_seconds", 5)),
                fps=int(opts.get("fps", 30)),
                resolution=opts.get("resolution", "1080p"),
                theme=opts.get("theme", "dark"),
                camera_style=opts.get("camera_style", "pan"),
                outro_text=opts.get("outro_text", "THE END"),
                progress=emit,
            )

        if summary["status"] != "ok":
            raise RuntimeError(summary.get("error", "video creation failed"))

        name = Path(summary["video_path"]).name
        jobs[job_id].update(
            state="done",
            stage="done",
            video_url=f"/videos/{name}",
            summary=summary,
        )
    except Exception as exc:  # noqa: BLE001
        jobs[job_id].update(state="error", stage="error", error=str(exc))


@app.post("/api/generate")
async def generate(
    text: str | None = Form(default=None),
    audio: UploadFile | None = File(default=None),
    language: str = Form(default="auto"),
    resolution: str = Form(default="1080p"),
    camera: str = Form(default="pan"),
    theme: str = Form(default="dark"),
    seconds: str = Form(default="5"),
    outro: str = Form(default="THE END"),
) -> JSONResponse:
    if not text and audio is None:
        raise HTTPException(status_code=400, detail="Provide text or an audio file")

    job_id = uuid.uuid4().hex[:12]
    audio_path = None
    if audio is not None:
        suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
        audio_path = UPLOAD_DIR / f"upload_{job_id}{suffix}"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(await audio.read())

    jobs[job_id] = {"state": "queued", "stage": "queued"}
    options = {
        "resolution": resolution,
        "camera_style": camera,
        "theme": theme,
        "scene_seconds": seconds,
        "outro_text": outro,
    }
    threading.Thread(
        target=_run_job,
        args=(job_id, text, audio_path, language, options),
        daemon=True,
    ).start()
    return JSONResponse({"job_id": job_id})


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> JSONResponse:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JSONResponse(job)


@app.get("/videos/{name}")
def video(name: str) -> FileResponse:
    path = OUT_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="video not found")
    return FileResponse(path, media_type="video/mp4")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)