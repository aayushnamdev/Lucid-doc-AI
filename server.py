"""Lucid server — FastAPI backend + serves the web frontend."""

import asyncio
import json
import concurrent.futures
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

OUTPUT_DIR = Path("output")
WEB_DIR = Path("web")

app = FastAPI(title="Lucid")

_jobs: dict[str, asyncio.Queue] = {}
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


class GenerateRequest(BaseModel):
    repo_url: str
    audience: str | None = None


@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")


@app.post("/generate")
async def start_generate(req: GenerateRequest):
    job_id = f"{id(req):x}"
    queue: asyncio.Queue = asyncio.Queue()
    _jobs[job_id] = queue

    loop = asyncio.get_event_loop()

    def on_progress(msg: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, msg)

    def worker():
        try:
            from lucid.pipeline import run
            run(req.repo_url, OUTPUT_DIR, on_progress, audience=req.audience)
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, f"fatal:{e}")

    loop.run_in_executor(_executor, worker)
    return {"job_id": job_id}


@app.get("/events/{job_id}")
async def event_stream(job_id: str):
    queue = _jobs.get(job_id)
    if queue is None:
        raise HTTPException(404, "Job not found")

    async def generate():
        terminal = {"finished", "no_python_files"}
        while True:
            msg = await queue.get()
            yield f"data: {json.dumps({'msg': msg})}\n\n"
            if msg in terminal or msg.startswith("fatal:"):
                _jobs.pop(job_id, None)
                break

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/files")
async def list_docs():
    if not OUTPUT_DIR.exists():
        return {"files": []}
    files = [str(p.relative_to(OUTPUT_DIR)) for p in sorted(OUTPUT_DIR.rglob("*.md"))]
    return {"files": files}


@app.get("/doc")
async def get_doc(path: str):
    target = (OUTPUT_DIR / path).resolve()
    if not str(target).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(403, "Access denied")
    if not target.exists():
        raise HTTPException(404, "Not found")
    return {"content": target.read_text(encoding="utf-8")}
