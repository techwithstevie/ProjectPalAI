"""
ProjectPalAI tutorial generator.

Local Ollama only (default client → 127.0.0.1:11434). No OLLAMA_HOST.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Callable, Dict, List, Optional

import ollama
from pydantic import ValidationError

from schema import (
    BuildStep,
    Difficulty,
    ProjectSize,
    ProjectTutorial,
    coerce_hours,
)

DEFAULT_MODEL = os.environ.get("PROJECTPALAI_MODEL", "gpt-oss:120b-cloud")

# hours is a SINGLE float (never a range tuple).
# steps_lo / steps_hi are separate ints so nothing can float() a pair.
SIZE_TARGETS: Dict[ProjectSize, Dict[str, Any]] = {
    "small": {
        "steps_lo": 8,
        "steps_hi": 12,
        "hours": 3.0,
        "code_ratio": 0.7,
        "checkpoints_every": 3,
    },
    "medium": {
        "steps_lo": 14,
        "steps_hi": 20,
        "hours": 9.0,
        "code_ratio": 0.75,
        "checkpoints_every": 3,
    },
    "monolithic": {
        "steps_lo": 24,
        "steps_hi": 36,
        "hours": 30.0,
        "code_ratio": 0.8,
        "checkpoints_every": 4,
    },
}

_HARMONY_CHANNEL = re.compile(
    r"<\|channel\|>\s*analysis\s*<\|message\|>.*?(?:<\|end\|>|<\|start\|>)",
    re.DOTALL,
)
_HARMONY_FINAL = re.compile(r"<\|channel\|>\s*final\s*<\|message\|>", re.IGNORECASE)
_HARMONY_TAGS = re.compile(r"<\|[a-z_]+\|>", re.IGNORECASE)


def _strip_harmony(raw: str) -> str:
    raw = _HARMONY_CHANNEL.sub("", raw)
    m = _HARMONY_FINAL.search(raw)
    if m:
        raw = raw[m.end() :]
    return _HARMONY_TAGS.sub("", raw).strip()


def extract_json(raw: str) -> str:
    raw = _strip_harmony(raw or "")
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fence:
        return fence.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        return raw[start : end + 1]
    return raw


def chat_json(
    *,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.35,
    num_predict: int = 16384,
    schema: Optional[type] = None,
    max_retries: int = 3,
) -> dict:
    last_err: Exception | None = None

    for attempt in range(max_retries):
        try:
            kwargs: dict = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "options": {
                    "temperature": temperature,
                    "num_predict": num_predict,
                },
            }
            if schema is not None:
                try:
                    kwargs["format"] = schema.model_json_schema()
                except Exception:
                    kwargs["format"] = "json"
            else:
                kwargs["format"] = "json"

            try:
                response = ollama.chat(**kwargs, think=False)
            except TypeError:
                response = ollama.chat(**kwargs)

            raw = response["message"]["content"]
            if not str(raw).strip():
                raise ValueError("Empty model response")

            return json.loads(extract_json(str(raw)))
        except Exception as e:
            last_err = e
            print(f"[generator] chat_json attempt {attempt + 1} failed: {e}")

    raise RuntimeError(
        f"Ollama generation failed after {max_retries} attempts: {last_err}. "
        f"Is `ollama serve` running? model={model}"
    )


SYSTEM_OUTLINE = """You are ProjectPalAI, an expert educator who writes YouTube-style
project-based coding tutorials. You teach by building ONE real product end to end.

Rules:
- Output a single JSON object matching the ProjectTutorial shape (snake_case keys).
- Linear steps only — no modules, no courses, no charts, no slide decks.
- Modern stack only (Python 3.12+, current library APIs, pyproject.toml, type hints).
- Never use deprecated APIs.
- Pin dependency versions (e.g. >=2.2) — never "latest" alone.
- repo_layout MUST include: pyproject.toml, README.md, src/, tests/.
- Most steps ship real code into the same project (file_path under src/ or tests/).
- speaker_notes = full spoken transcript (teach while building).
- Mark is_checkpoint=true every few steps.
- Include intro_transcript, outro_transcript, how_to_run.
- final_project_code MUST be a single STRING (concatenate files with # --- path --- headers),
  never an object/dict.
- estimated_hours MUST be a single number (e.g. 3.0), never a range/array/tuple.
- challenges items MUST include: title, description, build_process, solution_code,
  solution_walkthrough (all strings). 0–2 challenges.
- difficulty and size must match the user request.
"""

SYSTEM_EXPAND_STEP = """You are ProjectPalAI expanding a single build step into full
tutorial quality. Return JSON for ONE BuildStep only (snake_case).

Requirements:
- Full speaker_notes transcript (at least ~120 words) teaching while coding.
- If code is appropriate, provide complete runnable CodeBlock with file_path under
  src/ or tests/ (or root config like pyproject.toml).
- bullets: 3–6 short on-screen points.
- files_touched must include code.file_path when code is present.
- Modern Python 3.12+, type hints, no legacy APIs.
- Keep step_number and title consistent with the request.
"""


def _default_hours(size: ProjectSize) -> float:
    return coerce_hours(SIZE_TARGETS[size]["hours"], default=4.0)


def _coerce_hours(v: Any, size: ProjectSize) -> float:
    return coerce_hours(v, default=_default_hours(size))


def _outline_user(
    topic: str,
    difficulty: Difficulty,
    size: ProjectSize,
) -> str:
    t = SIZE_TARGETS[size]
    lo = int(t["steps_lo"])
    hi = int(t["steps_hi"])
    mid_hours = coerce_hours(t["hours"], default=4.0)
    return f"""Create a complete ProjectTutorial JSON for this request.

Topic: {topic}
Difficulty: {difficulty}
Size: {size}
Target steps: {lo}–{hi}
Estimated hours: a SINGLE number {mid_hours} (not a list, not a range).

Include:
- title, tagline, description, difficulty, size, estimated_hours (single number {mid_hours})
- problem_statement, end_state
- prerequisites, learning_outcomes
- repo_layout (src layout + tests + pyproject.toml + README.md)
- stack (name, version pin, purpose) including python >=3.12
- best_practices
- intro_transcript
- steps[] with step_number, title, goal, bullets, speaker_notes, optional code,
  files_touched, is_checkpoint
- outro_transcript
- final_project_code as a STRING only (not an object)
- how_to_run
- challenges (0–2) each with title, description, build_process, solution_code, solution_walkthrough

Return ONLY valid JSON for ProjectTutorial (id may be empty string).
"""


def _expand_step_user(
    tutorial: ProjectTutorial,
    step: BuildStep,
    step_index: int,
) -> str:
    prev = tutorial.steps[step_index - 1] if step_index > 0 else None
    prev_info = ""
    if prev:
        prev_info = (
            f"Previous step: #{prev.step_number} {prev.title}\n"
            f"Prev files: {prev.files_touched}\n"
        )
    code_hint = ""
    if step.code:
        code_hint = (
            f"Existing code path: {step.code.file_path}\n"
            f"Existing code (improve/complete if needed):\n{step.code.code[:1500]}\n"
        )
    return f"""Expand this build step for project: {tutorial.title}
Difficulty: {tutorial.difficulty} · Size: {tutorial.size}
Stack: {[s.model_dump() for s in tutorial.stack[:8]]}
Repo layout: {tutorial.repo_layout[:20]}
{prev_info}
Step number: {step.step_number}
Title: {step.title}
Goal: {step.goal}
Current bullets: {step.bullets}
Current notes length: {len(step.speaker_notes or '')}
{code_hint}
is_checkpoint: {step.is_checkpoint}

Return a full BuildStep JSON with rich speaker_notes and solid code when appropriate.
"""


def _dict_code_to_string(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        parts = []
        for k, val in v.items():
            body = (
                val
                if isinstance(val, str)
                else json.dumps(val, indent=2, ensure_ascii=False)
            )
            parts.append(f"# --- {k} ---\n{body}")
        return "\n\n".join(parts)
    if isinstance(v, list):
        return "\n".join(_dict_code_to_string(x) for x in v)
    return str(v)


def _normalize_challenge(c: Any) -> dict:
    if not isinstance(c, dict):
        return {
            "title": "Challenge",
            "description": str(c),
            "build_process": str(c),
            "solution_code": "",
            "solution_walkthrough": "",
        }
    d = dict(c)
    title = d.get("title") or "Challenge"
    description = (
        d.get("description")
        or d.get("prompt")
        or d.get("task")
        or d.get("summary")
        or title
    )
    build_process = (
        d.get("build_process")
        or d.get("process")
        or d.get("guide")
        or d.get("approach")
        or d.get("instructions")
        or d.get("how_to_build")
        or d.get("hint")
        or description
    )
    if isinstance(build_process, (list, dict)):
        build_process = _dict_code_to_string(build_process)
    solution_code = (
        d.get("solution_code") or d.get("code") or d.get("reference_code") or ""
    )
    if isinstance(solution_code, dict):
        solution_code = _dict_code_to_string(solution_code)
    walkthrough = (
        d.get("solution_walkthrough")
        or d.get("walkthrough")
        or d.get("explanation")
        or d.get("solution_notes")
        or ""
    )
    return {
        "title": str(title),
        "description": str(description),
        "build_process": str(build_process),
        "solution_code": str(solution_code),
        "solution_walkthrough": str(walkthrough),
        "sample_output": d.get("sample_output"),
    }


def _normalize_tutorial_dict(
    data: dict,
    *,
    topic: str,
    difficulty: Difficulty,
    size: ProjectSize,
) -> dict:
    data = dict(data or {})
    data.setdefault("id", "")
    data.setdefault("title", topic.title() if topic else "Untitled Project")
    data.setdefault("tagline", "")
    data.setdefault("description", data.get("problem_statement") or "")
    data["difficulty"] = difficulty
    data["size"] = size
    # ALWAYS coerce — this kills the float(tuple) error
    data["estimated_hours"] = _coerce_hours(data.get("estimated_hours"), size)
    data.setdefault("problem_statement", f"Build: {topic}")
    data.setdefault("end_state", "A working project matching the stated goals.")
    data.setdefault("prerequisites", [])
    data.setdefault("learning_outcomes", [])
    data.setdefault("repo_layout", [])
    data.setdefault("stack", [])
    data.setdefault("best_practices", [])
    data.setdefault("intro_transcript", "")
    data.setdefault("outro_transcript", "")
    data.setdefault("how_to_run", "")
    data.setdefault("quality_report", None)

    data["final_project_code"] = _dict_code_to_string(data.get("final_project_code"))

    raw_ch = data.get("challenges") or []
    if not isinstance(raw_ch, list):
        raw_ch = []
    data["challenges"] = [_normalize_challenge(c) for c in raw_ch]

    steps = data.get("steps") or []
    fixed_steps = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        s = dict(s)
        sn = s.get("step_number")
        if isinstance(sn, (list, tuple)):
            sn = sn if sn else (i + 1)
        try:
            s["step_number"] = int(sn or (i + 1))
        except Exception:
            s["step_number"] = i + 1
        s.setdefault("title", f"Step {i + 1}")
        s.setdefault("goal", s.get("title") or "Advance the project")
        s.setdefault("bullets", [])
        s.setdefault("speaker_notes", s.get("notes") or s.get("transcript") or "")
        s.setdefault("files_touched", [])
        s.setdefault("is_checkpoint", bool(s.get("is_checkpoint", False)))
        code = s.get("code")
        if isinstance(code, dict):
            code = dict(code)
            if "file_path" not in code:
                for k in ("path", "filename", "file", "filepath"):
                    if k in code:
                        code["file_path"] = code[k]
                        break
            if "code" not in code:
                for k in ("content", "source", "body", "snippet"):
                    if k in code:
                        code["code"] = code[k]
                        break
            code.setdefault("language", "python")
            code.setdefault("file_path", f"src/step_{i + 1}.py")
            code.setdefault("code", "")
            code.setdefault("explanation", "")
            if isinstance(code.get("code"), dict):
                code["code"] = _dict_code_to_string(code["code"])
            s["code"] = code
        elif isinstance(code, str) and code.strip():
            s["code"] = {
                "language": "python",
                "file_path": f"src/step_{i + 1}.py",
                "code": code,
                "explanation": "",
            }
        else:
            s["code"] = None
        fixed_steps.append(s)
    data["steps"] = fixed_steps
    return data


def _ensure_min_layout(tutorial: ProjectTutorial) -> ProjectTutorial:
    layout = list(tutorial.repo_layout or [])
    joined = " ".join(layout).lower()
    for entry in ("pyproject.toml", "README.md", "src/", "tests/"):
        key = entry.rstrip("/").lower()
        if key not in joined:
            layout.append(entry)
            joined += " " + key
    tutorial.repo_layout = layout
    return tutorial


def expand_steps(
    tutorial: ProjectTutorial,
    *,
    model: str,
    progress_callback: Callable[[str], None] | None = None,
    expand_all: bool = False,
) -> ProjectTutorial:
    def log(msg: str):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    new_steps: List[BuildStep] = []
    total = len(tutorial.steps)

    for i, step in enumerate(tutorial.steps):
        notes = (step.speaker_notes or "").strip()
        code_body = ""
        if step.code and step.code.code:
            code_body = step.code.code.strip()

        needs = expand_all or len(notes) < 80 or (
            step.code is not None and len(code_body) < 30
        )
        if not needs:
            new_steps.append(step)
            continue

        log(f"Expanding step {i + 1}/{total}: {step.title}…")
        try:
            raw = chat_json(
                model=model,
                system=SYSTEM_EXPAND_STEP,
                user=_expand_step_user(tutorial, step, i),
                temperature=0.3,
                num_predict=6144,
                schema=BuildStep,
            )
            if "step_number" not in raw:
                raw["step_number"] = step.step_number
            expanded = BuildStep.model_validate(raw)
            expanded.step_number = step.step_number
            if not expanded.title:
                expanded.title = step.title
            new_steps.append(expanded)
        except Exception as e:
            log(f"Step expand failed ({step.title}): {e} — keeping draft")
            new_steps.append(step)

    tutorial.steps = new_steps
    return tutorial


def generate_tutorial(
    topic: str,
    difficulty: Difficulty = "intermediate",
    size: ProjectSize = "medium",
    model: str = DEFAULT_MODEL,
    progress_callback: Callable[[str], None] | None = None,
    run_agents: bool = True,
    use_llm_review: bool = True,
    use_llm_repair: bool = True,
    expand_thin_steps: bool = True,
) -> ProjectTutorial:
    def log(msg: str):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    topic = (topic or "").strip()
    if not topic:
        raise ValueError("topic is required")
    if size not in SIZE_TARGETS:
        size = "medium"
    if difficulty not in ("beginner", "intermediate", "advanced"):
        difficulty = "intermediate"

    targets = SIZE_TARGETS[size]
    lo = int(targets["steps_lo"])
    hi = int(targets["steps_hi"])
    log(
        f'Generating {size} / {difficulty} tutorial for "{topic}" '
        f"(target {lo}–{hi} steps)…"
    )
    log(f"Ollama model={model} (local default client)")

    log("Drafting full tutorial outline…")
    raw = chat_json(
        model=model,
        system=SYSTEM_OUTLINE,
        user=_outline_user(topic, difficulty, size),
        temperature=0.4,
        num_predict=20000,
        schema=ProjectTutorial,
        max_retries=3,
    )
    raw = _normalize_tutorial_dict(raw, topic=topic, difficulty=difficulty, size=size)

    try:
        tutorial = ProjectTutorial.model_validate(raw)
    except ValidationError as e:
        log(f"Validation issues on draft, retrying normalize: {e}")
        steps_ok = []
        for s in raw.get("steps") or []:
            try:
                steps_ok.append(BuildStep.model_validate(s).model_dump())
            except Exception as se:
                log(f"Dropping invalid step: {se}")
                continue
        raw["steps"] = steps_ok
        raw["final_project_code"] = _dict_code_to_string(raw.get("final_project_code"))
        raw["challenges"] = [
            _normalize_challenge(c) for c in (raw.get("challenges") or [])
        ]
        raw["estimated_hours"] = _coerce_hours(raw.get("estimated_hours"), size)
        try:
            tutorial = ProjectTutorial.model_validate(raw)
        except ValidationError as e2:
            log(f"Still invalid after normalize: {e2}")
            safe_hours = _coerce_hours(raw.get("estimated_hours"), size)
            tutorial = ProjectTutorial(
                title=str(raw.get("title") or topic.title()),
                tagline=str(raw.get("tagline") or ""),
                description=str(raw.get("description") or ""),
                difficulty=difficulty,
                size=size,
                estimated_hours=safe_hours,
                problem_statement=str(
                    raw.get("problem_statement") or f"Build: {topic}"
                ),
                end_state=str(raw.get("end_state") or "A working project."),
                steps=[BuildStep.model_validate(s) for s in steps_ok]
                if steps_ok
                else [
                    BuildStep(
                        step_number=1,
                        title="Scaffold the project",
                        goal="Create layout and entrypoint",
                        bullets=["Create src layout", "Add pyproject.toml"],
                        speaker_notes=(
                            "We start by scaffolding a modern Python project with a src "
                            "layout, tests, and a pinned dependency set. Follow along as "
                            "we create the skeleton, then build features step by step."
                        ),
                        files_touched=["pyproject.toml", "src/", "tests/"],
                        is_checkpoint=True,
                    )
                ],
                final_project_code=_dict_code_to_string(raw.get("final_project_code")),
                how_to_run=str(
                    raw.get("how_to_run") or "pip install -e .\npytest -q\n"
                ),
            )

    tutorial = _ensure_min_layout(tutorial)
    if not tutorial.id:
        tutorial.id = str(uuid.uuid4())

    # Force hours one more time after any agent/model path
    tutorial.estimated_hours = coerce_hours(
        tutorial.estimated_hours, default=_default_hours(size)
    )

    log(f"Draft ready: {len(tutorial.steps)} steps · {tutorial.title}")

    if expand_thin_steps and tutorial.steps:
        log("Polishing thin steps…")
        tutorial = expand_steps(
            tutorial,
            model=model,
            progress_callback=progress_callback,
            expand_all=False,
        )

    if run_agents:
        log("Running quality agents (structure · practices · code · repair)…")
        try:
            from agents.pipeline import run_quality_pipeline

            tutorial, report = run_quality_pipeline(
                tutorial,
                model=model,
                use_llm_review=use_llm_review,
                use_llm_repair=use_llm_repair,
                progress_callback=progress_callback,
            )
            tutorial.estimated_hours = coerce_hours(
                tutorial.estimated_hours, default=_default_hours(size)
            )
            try:
                tutorial.quality_report = report.model_dump()
            except Exception:
                tutorial.quality_report = {
                    "passed": getattr(report, "passed", False),
                    "score": getattr(report, "score", 0),
                    "findings_count": getattr(report, "findings_count", 0),
                    "error_count": getattr(report, "error_count", 0),
                    "warning_count": getattr(report, "warning_count", 0),
                }
            log(
                f"Agents finished — score {report.score:.0f}/100, "
                f"{report.findings_count} open finding(s) after repair"
            )
        except Exception as e:
            log(f"Quality pipeline error (returning draft): {e}")
            tutorial.quality_report = {
                "passed": False,
                "score": 0,
                "findings_count": 0,
                "error_count": 1,
                "warning_count": 0,
                "reviews": [],
                "repair": {
                    "applied": False,
                    "summary": f"Pipeline error: {e}",
                    "actions": [],
                    "remaining_issues": [str(e)],
                },
            }
    else:
        log("Quality agents skipped (run_agents=false)")

    for i, step in enumerate(tutorial.steps):
        step.step_number = i + 1

    tutorial.estimated_hours = coerce_hours(
        tutorial.estimated_hours, default=_default_hours(size)
    )

    log(f"Ready: {len(tutorial.steps)} steps · {tutorial.title}")
    return tutorial


def generate_course(*args, **kwargs) -> ProjectTutorial:
    return generate_tutorial(*args, **kwargs)