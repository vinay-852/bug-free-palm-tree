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
  textarea {
    width:100%; box-sizing:border-box; padding:14px; border-radius:10px;
    border:1px solid #22304e; background:#131c2e; color:#e2e8f0; font-size:15px;
    min-height:130px; resize:vertical; font:inherit;
  }
  .tabs { display:flex; gap:10px; margin:26px 0 14px; }
  .tab { flex:1; min-height:54px; padding:12px; text-align:center; border-radius:12px; cursor:pointer;
         border:1px solid #22304e; background:#131c2e; color:#94a3b8; font-weight:700; font-size:15px; }
  .tab.active { background:#22d3ee; color:#0b1220; border-color:#22d3ee; }
  .panel { display:none; }
  .panel.active { display:block; }
  .record-wrap { display:flex; flex-direction:column; align-items:center; justify-content:center;
                 min-height:150px; gap:12px; border:1px solid #22304e; border-radius:12px;
                 background:#131c2e; }
  .recbtn { width:68px; height:68px; margin:0; padding:0; border:0; border-radius:50%; cursor:pointer;
            background:#22d3ee; color:#0b1220; font-size:28px; }
  .recbtn.recording { background:#ef4444; animation: pulse 1s infinite; }
  @keyframes pulse { 50% { opacity:.55; } }
  .timer { color:#94a3b8; font-size:14px; }
  #recorded { color:#34d399; font-size:13px; }
  .generate { width:100%; padding:14px; margin-top:18px; border:0; border-radius:10px;
           background:#22d3ee; color:#0b1220; font-size:16px; font-weight:800; cursor:pointer; }
  button:disabled { opacity:.5; cursor:wait; }
  #status { margin-top:18px; color:#94a3b8; font-size:14px; white-space:pre-line; }
  #result { margin-top:18px; }
  video { width:100%; border-radius:12px; background:#000; }
  .err { color:#f87171; font-weight:600; }
</style>
</head>
<body>
<div class="card">
  <h1>Video Agent</h1>
  <p class="sub">Type an idea or record it. The agent creates the video.</p>
  {{DRY_NOTE}}

  <div class="tabs">
    <button type="button" class="tab active" id="tab-text" onclick="switchTab('text')">✍️ &nbsp;Text</button>
    <button type="button" class="tab" id="tab-audio" onclick="switchTab('audio')">🎙️ &nbsp;Record audio</button>
  </div>

  <div class="panel active" id="panel-text">
    <textarea id="topic" placeholder="Describe the video you want..."></textarea>
  </div>
  <div class="panel" id="panel-audio">
    <div class="record-wrap">
      <button type="button" class="recbtn" id="record" aria-label="Start recording" onclick="toggleRecord()">🎙️</button>
      <div class="timer" id="timer">Tap to record (up to 60 seconds)</div>
      <div id="recorded"></div>
    </div>
  </div>

  <button class="generate" id="go" onclick="generate()">Create video</button>
  <div id="status"></div>
  <div id="result"></div>
</div>

<script>
let recorder = null, chunks = [], recordStart = 0, timerInt = null;

function switchTab(which) {
  document.getElementById('tab-text').classList.toggle('active', which==='text');
  document.getElementById('tab-audio').classList.toggle('active', which==='audio');
  document.getElementById('panel-text').classList.toggle('active', which==='text');
  document.getElementById('panel-audio').classList.toggle('active', which==='audio');
}

async function toggleRecord() {
  const btn = document.getElementById('record');
  if (recorder) { stopRecord(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    chunks = [];
    const activeRecorder = new MediaRecorder(stream);
    recorder = activeRecorder;
    activeRecorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    activeRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(chunks, {type: activeRecorder.mimeType || 'audio/webm'});
      const file = new File([blob], 'recording.webm', {type: blob.type});
      window.recordedAudio = file;
      document.getElementById('recorded').textContent =
        'Ready — ' + Math.round((Date.now()-recordStart)/1000) + ' seconds recorded';
      document.getElementById('timer').textContent = 'Recording saved';
    };
    activeRecorder.start();
    recordStart = Date.now();
    btn.textContent = '⏹️';
    btn.setAttribute('aria-label', 'Stop recording');
    btn.classList.add('recording');
    timerInt = setInterval(() => {
      const s = Math.floor((Date.now()-recordStart)/1000);
      document.getElementById('timer').textContent =
        String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0');
      if (s >= 60) stopRecord(); // STT REST limit
    }, 250);
  } catch (e) {
    alert('Microphone not available: ' + e.message);
  }
}
function stopRecord() {
  if (!recorder) return;
  clearInterval(timerInt);
  recorder.stop();
  recorder = null;
  const btn = document.getElementById('record');
  btn.textContent = '🎙️';
  btn.setAttribute('aria-label', 'Start recording');
  btn.classList.remove('recording');
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
    const file = window.recordedAudio;
    if (!file) { alert('Record a voice note first'); go.disabled = false; return; }
    form.append('audio', file);
  }

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
    from video_agent.runtime import dry_run

    note = ""
    if dry_run():
        note = ('<p class="hint" style="color:#f59e0b;border:1px solid #f59e0b;'
                'padding:8px 12px;border-radius:8px;">DRY RUN: Gemini and Gnani are '
                'mocked (heuristic plan, silent narration, canned transcript). '
                'Set DRY_RUN=0 for real generation.</p>')
    return PAGE.replace("{{DRY_NOTE}}", note)


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
    threading.Thread(
        target=_run_job,
        args=(job_id, text, audio_path, "auto", {}),
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