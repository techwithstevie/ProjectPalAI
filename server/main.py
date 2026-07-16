"""
ProjectPalAI API — YouTube-style project tutorial generator.

Topic + difficulty + size → linear build steps, then quality agents
review structure / best practices / code and auto-repair issues.
"""
from __future__ import annotations

import json
import queue
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from generator import generate_tutorial
from schema import ProjectTutorial
from pptx_export import export_tutorial_to_pptx

app = FastAPI(title="ProjectPalAI", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "generated_tutorials"
DATA_DIR.mkdir(exist_ok=True)

EXPORT_DIR = Path(__file__).parent / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

Difficulty = Literal["beginner", "intermediate", "advanced"]
ProjectSize = Literal["small", "medium", "monolithic"]


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=2)
    difficulty: Difficulty = "intermediate"
    size: ProjectSize = "medium"
    # Legacy aliases
    audience_level: Difficulty | None = None
    project_size: ProjectSize | None = None
    # Quality agents
    run_agents: bool = Field(
        default=True,
        description="Run structure / practices / code review + repair after generation",
    )
    use_llm_review: bool = Field(
        default=True,
        description="Use LLM for deep review (rules always run)",
    )
    use_llm_repair: bool = Field(
        default=True,
        description="Allow LLM full repair when deterministic fixes are not enough",
    )


def _resolve_params(req: GenerateRequest) -> tuple[str, Difficulty, ProjectSize]:
    difficulty: Difficulty = req.audience_level or req.difficulty
    size: ProjectSize = req.project_size or req.size
    return req.topic.strip(), difficulty, size


def _save(tutorial: ProjectTutorial) -> ProjectTutorial:
    if not tutorial.id:
        tutorial.id = str(uuid.uuid4())
    path = DATA_DIR / f"{tutorial.id}.json"
    path.write_text(tutorial.model_dump_json(indent=2), encoding="utf-8")
    return tutorial


def _load(tutorial_id: str) -> ProjectTutorial:
    path = DATA_DIR / f"{tutorial_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Tutorial not found")
    return ProjectTutorial.model_validate_json(path.read_text(encoding="utf-8"))


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/health")
def health():
    return {
        "ok": True,
        "product": "ProjectPalAI",
        "mode": "project-tutorial",
        "agents": ["structure", "practices", "code", "repair"],
        "version": "3.1.0",
    }


@app.post("/api/generate")
def generate(req: GenerateRequest):
    topic, difficulty, size = _resolve_params(req)
    tutorial = generate_tutorial(
        topic=topic,
        difficulty=difficulty,
        size=size,
        run_agents=req.run_agents,
        use_llm_review=req.use_llm_review,
        use_llm_repair=req.use_llm_repair,
    )
    return _save(tutorial)


@app.post("/api/generate/stream")
def generate_stream(req: GenerateRequest):
    topic, difficulty, size = _resolve_params(req)

    def event_stream():
        q: queue.Queue = queue.Queue()

        def on_progress(message: str):
            q.put(("status", message))

        def worker():
            try:
                tutorial = generate_tutorial(
                    topic=topic,
                    difficulty=difficulty,
                    size=size,
                    progress_callback=on_progress,
                    run_agents=req.run_agents,
                    use_llm_review=req.use_llm_review,
                    use_llm_repair=req.use_llm_repair,
                )
                tutorial = _save(tutorial)
                q.put(("complete", tutorial.model_dump()))
            except Exception as e:
                q.put(("error", str(e)))

        yield _sse(
            {
                "type": "status",
                "message": f'ProjectPalAI starting {size} tutorial for "{topic}"…',
            }
        )

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while True:
            try:
                kind, payload = q.get(timeout=0.5)
            except queue.Empty:
                if not thread.is_alive():
                    while not q.empty():
                        kind, payload = q.get_nowait()
                        if kind == "status":
                            yield _sse({"type": "status", "message": payload})
                        elif kind == "complete":
                            yield _sse({"type": "complete", "tutorial": payload})
                            return
                        elif kind == "error":
                            yield _sse({"type": "error", "message": payload})
                            return
                    yield _sse(
                        {"type": "error", "message": "Generation ended unexpectedly"}
                    )
                    return
                continue

            if kind == "status":
                yield _sse({"type": "status", "message": payload})
            elif kind == "complete":
                yield _sse({"type": "complete", "tutorial": payload})
                return
            elif kind == "error":
                yield _sse({"type": "error", "message": payload})
                return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/tutorials/{tutorial_id}")
def get_tutorial(tutorial_id: str):
    return _load(tutorial_id)


@app.get("/api/courses/{tutorial_id}")
def get_tutorial_legacy(tutorial_id: str):
    return _load(tutorial_id)


@app.get("/api/tutorials/{tutorial_id}/export")
def export_tutorial(tutorial_id: str):
    tutorial = _load(tutorial_id)
    out = EXPORT_DIR / f"{tutorial_id}.pptx"
    export_tutorial_to_pptx(tutorial, str(out))
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in tutorial.title[:40]
    )
    return FileResponse(
        path=str(out),
        filename=f"{safe_name or 'projectpalai'}.pptx",
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".presentationml.presentation"
        ),
    )


@app.get("/api/courses/{tutorial_id}/export")
def export_tutorial_legacy(tutorial_id: str):
    return export_tutorial(tutorial_id)


@app.get("/api/tutorials")
def list_tutorials():
    items = []
    for path in sorted(
        DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            qr = data.get("quality_report") or {}
            items.append(
                {
                    "id": data.get("id") or path.stem,
                    "title": data.get("title"),
                    "difficulty": data.get("difficulty"),
                    "size": data.get("size"),
                    "steps": len(data.get("steps") or []),
                    "quality_score": qr.get("score"),
                    "quality_passed": qr.get("passed"),
                }
            )
        except Exception:
            continue
    return {"tutorials": items}


@app.post("/api/tutorials/{tutorial_id}/review")
def re_run_agents(tutorial_id: str, use_llm_review: bool = True, use_llm_repair: bool = True):
    """Re-run quality agents on an existing saved tutorial and overwrite it."""
    from agents.pipeline import run_quality_pipeline

    tutorial = _load(tutorial_id)
    fixed, report = run_quality_pipeline(
        tutorial,
        use_llm_review=use_llm_review,
        use_llm_repair=use_llm_repair,
    )
    try:
        fixed.quality_report = report.model_dump()
    except Exception:
        fixed.quality_report = report.model_dump() if hasattr(report, "model_dump") else None
    if not fixed.id:
        fixed.id = tutorial_id
    return _save(fixed)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=5001, reload=True)