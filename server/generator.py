"""
Generate a single YouTube-style project tutorial.

No modules, no charts. Topic + difficulty + size → linear build steps
with full spoken transcripts and project code.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

import ollama
from schema import ProjectTutorial, ProjectSize, Difficulty

SIZE_GUIDE = {
    "small": {
        "steps": "8-12",
        "hours": "2-4",
        "scope": "one focused feature set, few files, quick win",
    },
    "medium": {
        "steps": "14-20",
        "hours": "6-12",
        "scope": "multi-module src layout, tests, clear architecture",
    },
    "monolithic": {
        "steps": "24-36",
        "hours": "20-40",
        "scope": "full product: data, core logic, CLI/API, eval, docs, packaging",
    },
}

MODERN_STACK = """
Use current (2025–2026) practices:
- Python 3.12+, pyproject.toml, pathlib, type hints
- pandas >=2.2, numpy >=2, scikit-learn >=1.5 when ML is relevant
- Prefer Pipeline / composition; no deprecated APIs
- src/ layout, pytest-friendly structure
- NEVER invent charts or matplotlib demo plots as teaching devices
"""

SYSTEM_PROMPT = f"""Reasoning: low

You write YouTube-style coding tutorials: the viewer learns ONLY by building
one project, step by step. Each step ships real code into a repo.

{MODERN_STACK}

speaker_notes = full oral transcript (what the instructor says on camera).
Respond with ONLY valid JSON, snake_case fields, no markdown fences.
"""

HARMONY_CHANNEL_PATTERN = re.compile(
    r"<\|channel\|>\s*analysis\s*<\|message\|>.*?(?:<\|end\|>|<\|start\|>)",
    re.DOTALL,
)
HARMONY_FINAL_MARKER = re.compile(
    r"<\|channel\|>\s*final\s*<\|message\|>", re.IGNORECASE
)
HARMONY_STRAY_TAGS = re.compile(r"<\|[a-z_]+\|>", re.IGNORECASE)

FIELD_ALIASES = {
    "courseTitle": "title",
    "audience": "difficulty",
    "audience_level": "difficulty",
    "audienceLevel": "difficulty",
    "projectSize": "size",
    "project_size": "size",
    "estimatedHours": "estimated_hours",
    "problemStatement": "problem_statement",
    "endState": "end_state",
    "learningOutcomes": "learning_outcomes",
    "repoLayout": "repo_layout",
    "bestPractices": "best_practices",
    "introTranscript": "intro_transcript",
    "outroTranscript": "outro_transcript",
    "finalProjectCode": "final_project_code",
    "howToRun": "how_to_run",
    "stepNumber": "step_number",
    "speakerNotes": "speaker_notes",
    "filesTouched": "files_touched",
    "isCheckpoint": "is_checkpoint",
    "filePath": "file_path",
    "expectedOutput": "expected_output",
    "bestPracticeNotes": "best_practice_notes",
    "buildProcess": "build_process",
    "solutionCode": "solution_code",
    "solutionWalkthrough": "solution_walkthrough",
    "sampleOutput": "sample_output",
    "codeExample": "code",
    "code_example": "code",
}


def _camel_to_snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch.lower() if ch.isupper() else ch)
    return "".join(out)


def _rename_keys(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_rename_keys(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    renamed = {}
    for key, value in obj.items():
        if key in FIELD_ALIASES:
            new_key = FIELD_ALIASES[key]
        else:
            snake = _camel_to_snake(str(key))
            new_key = FIELD_ALIASES.get(snake, snake)
        if new_key in renamed and renamed[new_key] not in (None, "", [], {}):
            continue
        renamed[new_key] = _rename_keys(value)
    return renamed


def _strip_harmony(raw: str) -> str:
    raw = HARMONY_CHANNEL_PATTERN.sub("", raw)
    m = HARMONY_FINAL_MARKER.search(raw)
    if m:
        raw = raw[m.end() :]
    return HARMONY_STRAY_TAGS.sub("", raw).strip()


def _extract_json(raw: str) -> str:
    raw = _strip_harmony(raw)
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fence:
        return fence.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        return raw[start : end + 1]
    return raw


def _normalize_code(code) -> dict | None:
    if code is None:
        return None
    if isinstance(code, str):
        if not code.strip():
            return None
        return {
            "language": "python",
            "file_path": "src/main.py",
            "code": code,
            "explanation": "Code for this build step.",
            "expected_output": "",
            "best_practice_notes": "",
        }
    if not isinstance(code, dict):
        return None
    code = _rename_keys(code)
    # nested {code: "..."} sometimes
    if "code" in code and isinstance(code["code"], dict):
        code = {**code, **_rename_keys(code["code"])}
    body = str(code.get("code") or "")
    if not body.strip():
        return None
    return {
        "language": "python",
        "file_path": str(code.get("file_path") or "src/main.py"),
        "code": body,
        "explanation": str(code.get("explanation") or ""),
        "expected_output": str(code.get("expected_output") or ""),
        "best_practice_notes": str(code.get("best_practice_notes") or ""),
    }


def _normalize_step(step: dict, index: int) -> dict:
    step = _rename_keys(step)
    try:
        step["step_number"] = int(step.get("step_number") or index + 1)
    except (TypeError, ValueError):
        step["step_number"] = index + 1
    step["title"] = str(step.get("title") or f"Step {step['step_number']}")
    step["goal"] = str(step.get("goal") or step["title"])
    bullets = step.get("bullets") or []
    if not isinstance(bullets, list):
        bullets = [str(bullets)]
    step["bullets"] = [str(b) for b in bullets]
    step["speaker_notes"] = str(step.get("speaker_notes") or "").strip()
    if len(step["speaker_notes"]) < 40:
        step["speaker_notes"] = (
            f"In this step we work on {step['title']}. "
            f"Goal: {step['goal']}. Follow the code carefully and run it before continuing."
        )
    files = step.get("files_touched") or []
    if not isinstance(files, list):
        files = [str(files)]
    step["files_touched"] = [str(f) for f in files]
    step["code"] = _normalize_code(
        step.get("code") or step.get("code_example")
    )
    if step["code"] and not step["files_touched"]:
        step["files_touched"] = [step["code"]["file_path"]]
    step["is_checkpoint"] = bool(step.get("is_checkpoint"))
    return step


def _normalize_challenge(c: dict) -> dict:
    c = _rename_keys(c)
    c["title"] = str(c.get("title") or "Challenge")
    c["description"] = str(c.get("description") or "")
    c["build_process"] = str(
        c.get("build_process")
        or "Extend the project, run it, then compare with the solution."
    )
    c["solution_code"] = str(
        c.get("solution_code")
        or 'print("challenge solution")\n'
    )
    c["solution_walkthrough"] = str(
        c.get("solution_walkthrough") or "See solution_code."
    )
    c["sample_output"] = str(c.get("sample_output") or "")
    return c


def _normalize_tutorial(data: dict, topic: str, difficulty: str, size: str) -> dict:
    data = _rename_keys(data)
    data["title"] = str(data.get("title") or f"Build: {topic}")
    data["tagline"] = str(data.get("tagline") or "")
    data["description"] = str(data.get("description") or data["title"])
    d = str(data.get("difficulty") or difficulty).lower()
    if d not in ("beginner", "intermediate", "advanced"):
        d = difficulty if difficulty in ("beginner", "intermediate", "advanced") else "intermediate"
    data["difficulty"] = d
    s = str(data.get("size") or size).lower()
    if s not in ("small", "medium", "monolithic"):
        s = size if size in SIZE_GUIDE else "medium"
    data["size"] = s
    try:
        data["estimated_hours"] = float(data.get("estimated_hours") or 4)
    except (TypeError, ValueError):
        data["estimated_hours"] = 4.0
    data["problem_statement"] = str(data.get("problem_statement") or data["description"])
    data["end_state"] = str(data.get("end_state") or "A working project the student can run.")
    for lk in ("prerequisites", "learning_outcomes", "repo_layout", "best_practices"):
        v = data.get(lk) or []
        if not isinstance(v, list):
            v = [str(v)]
        data[lk] = [str(x) for x in v]
    stack = data.get("stack") or []
    fixed_stack = []
    if isinstance(stack, list):
        for item in stack:
            if isinstance(item, str):
                fixed_stack.append(
                    {"name": item, "version": "latest", "purpose": ""}
                )
            elif isinstance(item, dict):
                item = _rename_keys(item)
                fixed_stack.append(
                    {
                        "name": str(item.get("name") or "package"),
                        "version": str(item.get("version") or "latest"),
                        "purpose": str(item.get("purpose") or ""),
                    }
                )
    if not fixed_stack:
        fixed_stack = [
            {"name": "python", "version": ">=3.12", "purpose": "Runtime"},
            {"name": "pytest", "version": ">=8.0", "purpose": "Tests"},
        ]
    data["stack"] = fixed_stack
    data["intro_transcript"] = str(data.get("intro_transcript") or "")
    data["outro_transcript"] = str(data.get("outro_transcript") or "")
    data["final_project_code"] = str(data.get("final_project_code") or "")
    data["how_to_run"] = str(data.get("how_to_run") or "python -m src.main")
    steps = data.get("steps") or []
    if not isinstance(steps, list):
        steps = []
    data["steps"] = [
        _normalize_step(st, i) for i, st in enumerate(steps) if isinstance(st, dict)
    ]
    # Ensure step numbers sequential
    for i, st in enumerate(data["steps"]):
        st["step_number"] = i + 1
    challenges = data.get("challenges") or []
    if not isinstance(challenges, list):
        challenges = []
    data["challenges"] = [
        _normalize_challenge(c) for c in challenges if isinstance(c, dict)
    ]
    return data


def _chat_json(
    model: str,
    user_prompt: str,
    max_retries: int = 2,
    num_predict: int = 16384,
    temperature: float = 0.2,
    normalize=None,
) -> ProjectTutorial:
    last_error = None
    for attempt in range(max_retries):
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            format=ProjectTutorial.model_json_schema(),
            think=False,
            options={"temperature": temperature, "num_predict": num_predict},
        )
        raw = response["message"]["content"]
        try:
            data = json.loads(_extract_json(raw))
            if normalize:
                data = normalize(data)
            return ProjectTutorial.model_validate(data)
        except Exception as e:
            last_error = e
            print(f"[generator] attempt {attempt + 1} failed: {e}")
            print(f"[generator] raw preview: {raw[:500]!r}")
    raise RuntimeError(f"Tutorial generation failed: {last_error}")


def generate_tutorial(
    topic: str,
    difficulty: Difficulty = "intermediate",
    size: ProjectSize = "medium",
    model: str = "gpt-oss:120b-cloud",
    progress_callback: Callable[[str], None] | None = None,
) -> ProjectTutorial:
    def log(msg: str):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    guide = SIZE_GUIDE.get(size, SIZE_GUIDE["medium"])
    log(f'Planning {size} project tutorial: "{topic}" ({difficulty})…')

    prompt = f"""
Create a complete YouTube-style PROJECT TUTORIAL.

Viewer builds ONE project from zero to working software.
NO modules. NO classes. NO charts/graphs. Linear steps only.

Topic / what to build: "{topic}"
Difficulty: {difficulty}
Size: {size}
Target steps: {guide['steps']}
Estimated hours: ~{guide['hours']}
Scope: {guide['scope']}

{MODERN_STACK}

JSON fields (snake_case):
title, tagline, description, difficulty, size, estimated_hours,
problem_statement, end_state, prerequisites, learning_outcomes,
repo_layout, stack (name, version, purpose), best_practices,
intro_transcript, steps, outro_transcript,
final_project_code, how_to_run, challenges

Each step:
step_number, title, goal, bullets (4-8 short),
speaker_notes (FULL YouTube transcript 300-600 words — teach by building),
code (object: language, file_path, code, explanation, expected_output, best_practice_notes)
  OR null only for pure setup/talk steps (max 2 without code),
files_touched, is_checkpoint (true every few steps when they should run)

Rules:
- Almost every step includes working Python code that advances the SAME project
- Code uses modern APIs; file_path matches repo_layout
- intro_transcript: 200-400 word channel-style intro
- outro_transcript: 150-300 word wrap-up + next ideas
- final_project_code: substantial combined exemplar
- challenges: 1-2 optional stretch tasks with full solution_code + build_process
- difficulty={difficulty}, size={size}

Return ONLY the ProjectTutorial JSON.
"""
    # Monolithic needs more tokens
    num_predict = {"small": 12288, "medium": 16384, "monolithic": 24576}.get(
        size, 16384
    )

    log("Generating full step-by-step tutorial (this can take a while)…")
    tutorial = _chat_json(
        model,
        prompt,
        num_predict=num_predict,
        normalize=lambda d: _normalize_tutorial(d, topic, difficulty, size),
    )

    # If model under-delivered steps for large sizes, expand in a second pass
    min_steps = {"small": 6, "medium": 12, "monolithic": 20}.get(size, 8)
    if len(tutorial.steps) < min_steps:
        log(
            f"Only {len(tutorial.steps)} steps — expanding to reach {size} depth…"
        )
        tutorial = _expand_steps(tutorial, topic, difficulty, size, model, min_steps)

    log(f"Ready: {len(tutorial.steps)} steps · {tutorial.title}")
    return tutorial


def _expand_steps(
    draft: ProjectTutorial,
    topic: str,
    difficulty: str,
    size: str,
    model: str,
    min_steps: int,
) -> ProjectTutorial:
    guide = SIZE_GUIDE[size]
    existing = [
        f"{s.step_number}. {s.title}" for s in draft.steps
    ]
    prompt = f"""
The tutorial is too short. Return a FULL ProjectTutorial JSON with at least {min_steps} steps
(target {guide['steps']}) for:

Topic: {topic}
Difficulty: {difficulty}
Size: {size}
Title: {draft.title}
Existing outline: {existing}

Rebuild the entire steps array in order — denser build steps, more code,
same single project. Keep intro_transcript, outro_transcript, stack, etc.
No charts. snake_case JSON only.
"""
    try:
        return _chat_json(
            model,
            prompt,
            num_predict=24576,
            normalize=lambda d: _normalize_tutorial(d, topic, difficulty, size),
        )
    except Exception as e:
        print(f"[expand_steps] failed: {e}")
        return draft


# ---- API compatibility shims (old names) ----

def generate_course(
    topic: str,
    audience_level: str = "intermediate",
    size: str = "medium",
    project_size: str | None = None,
    model: str = "gpt-oss:120b-cloud",
    progress_callback=None,
    **_ignored,
) -> ProjectTutorial:
    """main.py may still pass old kwargs; ignore modules/weeks/etc."""
    sz = project_size or size or "medium"
    if sz not in SIZE_GUIDE:
        sz = "medium"
    diff = audience_level if audience_level in (
        "beginner", "intermediate", "advanced"
    ) else "intermediate"
    return generate_tutorial(
        topic=topic,
        difficulty=diff,  # type: ignore
        size=sz,  # type: ignore
        model=model,
        progress_callback=progress_callback,
    )


def generate_lecture(topic: str, **kwargs) -> ProjectTutorial:
    return generate_course(topic, size="small", **kwargs)


if __name__ == "__main__":
    t = generate_tutorial("CLI todo app with SQLite", difficulty="beginner", size="small")
    print(t.model_dump_json(indent=2)[:2000])