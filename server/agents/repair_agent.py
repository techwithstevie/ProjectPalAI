"""Repair agent: deterministic fixes + optional LLM patch with normalization."""
from __future__ import annotations

from typing import Any, Callable, List

from schema import ProjectTutorial, coerce_hours

from .llm import chat_json_dict, tutorial_compact
from .models import Finding, RepairAction, RepairResult

DEFAULT_LAYOUT = [
    "pyproject.toml",
    "README.md",
    "src/",
    "src/__init__.py",
    "tests/",
    "tests/__init__.py",
]

DEFAULT_PRACTICES = [
    "src layout + pyproject.toml",
    "Type hints on public functions",
    "Pinned dependency versions",
    "pytest for core logic",
    "Documented how_to_run entrypoint",
    "Fixed seeds / reproducibility when randomness is used",
]


def _dump(t: Any) -> dict:
    return t.model_dump() if hasattr(t, "model_dump") else dict(t)


def _dict_code_to_string(v: Any) -> str:
    import json

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


def _guess_path_from_code(body: str, index: int) -> str:
    for line in (body or "").lstrip().splitlines()[:3]:
        line = line.strip()
        if line.startswith("#") and ("." in line or "/" in line):
            token = line.lstrip("#").strip().split().strip("()`'\"")
            if token.endswith((".py", ".toml", ".md")) or "/" in token:
                return token
    return f"src/step_{index + 1}.py"


def _normalize_step_code(code: Any, index: int) -> Any:
    if code is None or code is False or code == "":
        return None
    if isinstance(code, str):
        body = code
        if body.strip().startswith("```"):
            lines = body.strip().splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            body = "\n".join(lines)
        return {
            "language": "python",
            "file_path": _guess_path_from_code(body, index),
            "code": body,
            "explanation": "",
        }
    if isinstance(code, dict):
        d = dict(code)
        if "file_path" not in d:
            for k in ("path", "filename", "file", "filepath"):
                if k in d:
                    d["file_path"] = d[k]
                    break
        if "code" not in d:
            for k in ("content", "source", "body", "snippet"):
                if k in d:
                    d["code"] = d[k]
                    break
        if isinstance(d.get("code"), dict):
            d["code"] = _dict_code_to_string(d["code"])
        d.setdefault("language", "python")
        d.setdefault(
            "file_path",
            _guess_path_from_code(str(d.get("code") or ""), index),
        )
        d.setdefault("code", "")
        d.setdefault("explanation", "")
        return d
    return None


def normalize_tutorial_payload(
    data: dict, *, fallback: ProjectTutorial | None = None
) -> dict:
    data = dict(data or {})
    fb = _dump(fallback) if fallback is not None else {}

    def pick(key: str, default: Any = ""):
        v = data.get(key)
        if v is None or v == "":
            return fb.get(key, default)
        return v

    data["title"] = pick("title", "Untitled Project")
    data["tagline"] = pick("tagline", "")
    data["description"] = pick("description", "")
    data["difficulty"] = pick("difficulty", "intermediate")
    data["size"] = pick("size", "medium")

    eh = data.get("estimated_hours")
    if eh is None or eh == "":
        eh = fb.get("estimated_hours", 4.0)
    data["estimated_hours"] = coerce_hours(eh, default=4.0)

    data["problem_statement"] = pick(
        "problem_statement", pick("description", "Build the project")
    )
    data["end_state"] = pick("end_state", "A working project.")
    data["prerequisites"] = pick("prerequisites", []) or []
    data["learning_outcomes"] = pick("learning_outcomes", []) or []
    data["repo_layout"] = pick("repo_layout", []) or []
    data["stack"] = pick("stack", []) or []
    data["best_practices"] = pick("best_practices", []) or []
    data["intro_transcript"] = pick("intro_transcript", "")
    data["outro_transcript"] = pick("outro_transcript", "")
    data["how_to_run"] = pick("how_to_run", "")
    data["final_project_code"] = _dict_code_to_string(
        data.get("final_project_code")
        if data.get("final_project_code") not in (None, "")
        else fb.get("final_project_code")
    )
    data["challenges"] = (
        data.get("challenges")
        if isinstance(data.get("challenges"), list)
        else fb.get("challenges") or []
    )
    data["id"] = pick("id", fb.get("id") or "")
    data["quality_report"] = data.get("quality_report", fb.get("quality_report"))

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        steps = fb.get("steps") or []
    fixed = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        s = dict(s)
        sn = s.get("step_number")
        if isinstance(sn, (list, tuple)):
            sn = sn[0] if sn else (i + 1)
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
        s["code"] = _normalize_step_code(s.get("code"), i)
        if isinstance(s["code"], dict) and s["code"].get("file_path"):
            fp = s["code"]["file_path"]
            touched = [str(x) for x in (s.get("files_touched") or [])]
            if fp not in touched:
                touched.append(fp)
            s["files_touched"] = touched
        fixed.append(s)
    data["steps"] = fixed
    return data


def apply_deterministic_repairs(
    tutorial: ProjectTutorial,
    findings: List[Finding],
) -> tuple[ProjectTutorial, List[RepairAction]]:
    data = _dump(tutorial)
    actions: List[RepairAction] = []
    codes = {f.code for f in findings}

    # hours first — never leave a tuple
    data["estimated_hours"] = coerce_hours(data.get("estimated_hours"), default=4.0)

    layout = [str(x) for x in (data.get("repo_layout") or [])]
    layout_l = " ".join(layout).lower()
    for entry in DEFAULT_LAYOUT:
        key = entry.rstrip("/").lower()
        if key not in layout_l and entry.rstrip("/") not in layout:
            layout.append(entry)
            actions.append(
                RepairAction(
                    action="add_repo_layout_entry",
                    location="repo_layout",
                    detail=entry,
                )
            )
    data["repo_layout"] = layout

    stack = list(data.get("stack") or [])
    fixed_stack = []
    has_python = False
    for pkg in stack:
        if not isinstance(pkg, dict):
            continue
        name = str(pkg.get("name") or "package")
        if name.lower() in ("python", "python3"):
            has_python = True
        ver = str(pkg.get("version") or "").strip()
        if ver.lower() in ("", "latest", "*"):
            if "pandas" in name.lower():
                ver = ">=2.2"
            elif "numpy" in name.lower():
                ver = ">=2.0"
            elif "scikit" in name.lower() or name.lower() == "sklearn":
                name = "scikit-learn"
                ver = ">=1.5"
            elif "pytest" in name.lower():
                ver = ">=8.0"
            else:
                ver = ">=1.0"
            actions.append(
                RepairAction(
                    action="pin_dependency",
                    location=f"stack:{name}",
                    detail=ver,
                )
            )
        fixed_stack.append(
            {
                "name": name,
                "version": ver,
                "purpose": str(pkg.get("purpose") or ""),
            }
        )
    if not has_python:
        fixed_stack.insert(
            0,
            {"name": "python", "version": ">=3.12", "purpose": "Runtime"},
        )
        actions.append(
            RepairAction(
                action="add_python_runtime",
                location="stack",
                detail="python >=3.12",
            )
        )
    data["stack"] = fixed_stack

    practices = [str(p) for p in (data.get("best_practices") or [])]
    if len(practices) < 3 or "THIN_BEST_PRACTICES" in codes:
        for p in DEFAULT_PRACTICES:
            if p not in practices:
                practices.append(p)
        actions.append(
            RepairAction(
                action="expand_best_practices",
                location="best_practices",
                detail=f"{len(practices)} items",
            )
        )
    data["best_practices"] = practices

    if len(str(data.get("how_to_run") or "").strip()) < 10:
        data["how_to_run"] = (
            "# Install\npip install -e .\n# or: uv sync\n\n"
            "# Run\npython -m src.main\n\n# Tests\npytest -q\n"
        )
        actions.append(
            RepairAction(
                action="set_how_to_run",
                location="how_to_run",
                detail="default install/run/test commands",
            )
        )

    steps = list(data.get("steps") or [])
    for i, step in enumerate(steps):
        step["step_number"] = i + 1
        step["code"] = _normalize_step_code(step.get("code"), i)
        code = step.get("code")
        if isinstance(code, dict) and code.get("file_path"):
            fp = str(code["file_path"]).replace("\\", "/").lstrip("/")
            while fp.startswith("../"):
                fp = fp[3:]
            if (
                "/" not in fp
                and fp.endswith(".py")
                and fp not in ("main.py", "pyproject.toml")
            ):
                fp = f"src/{fp}"
                code["file_path"] = fp
                actions.append(
                    RepairAction(
                        action="normalize_file_path",
                        location=f"steps[{i}].code.file_path",
                        detail=fp,
                    )
                )
            else:
                code["file_path"] = fp
            touched = [str(x) for x in (step.get("files_touched") or [])]
            if fp not in touched:
                touched.append(fp)
                step["files_touched"] = touched
                actions.append(
                    RepairAction(
                        action="sync_files_touched",
                        location=f"steps[{i}].files_touched",
                        detail=fp,
                    )
                )
            step["code"] = code

        notes = str(step.get("speaker_notes") or "").strip()
        if len(notes) < 40:
            step["speaker_notes"] = (
                f"In this step we work on {step.get('title', 'the next piece')}. "
                f"Goal: {step.get('goal', 'advance the project')}. "
                "Open the project files listed, implement the code shown, "
                "run it, and confirm the output before moving on."
            )
            actions.append(
                RepairAction(
                    action="pad_speaker_notes",
                    location=f"steps[{i}].speaker_notes",
                    detail="minimum teaching transcript",
                )
            )

    if len(steps) >= 6 and not any(s.get("is_checkpoint") for s in steps):
        for i in range(2, len(steps), 3):
            steps[i]["is_checkpoint"] = True
        actions.append(
            RepairAction(
                action="add_checkpoints",
                location="steps",
                detail="every 3rd step from index 2",
            )
        )

    data["steps"] = steps

    if len(str(data.get("final_project_code") or "").strip()) < 40:
        chunks = []
        for s in steps:
            c = s.get("code")
            if isinstance(c, dict) and c.get("code"):
                chunks.append(
                    f"# --- {c.get('file_path', 'module.py')} ---\n{c['code']}\n"
                )
        if chunks:
            data["final_project_code"] = "\n".join(chunks)[:12000]
            actions.append(
                RepairAction(
                    action="compose_final_project_code",
                    location="final_project_code",
                    detail=f"from {len(chunks)} step(s)",
                )
            )

    data = normalize_tutorial_payload(data, fallback=tutorial)
    data["estimated_hours"] = coerce_hours(data.get("estimated_hours"), default=4.0)
    repaired = ProjectTutorial.model_validate(data)
    return repaired, actions


def repair_with_llm(
    tutorial: ProjectTutorial,
    findings: List[Finding],
    *,
    model: str,
    log: Callable[[str], None] | None = None,
) -> tuple[ProjectTutorial, RepairResult]:
    def _log(m: str):
        if log:
            log(m)

    tutorial, actions = apply_deterministic_repairs(tutorial, findings)
    _log(f"Deterministic repair applied {len(actions)} action(s)")

    remaining = [
        f
        for f in findings
        if f.severity in ("error", "warning")
        and f.code
        not in {
            "MISSING_LAYOUT_ENTRY",
            "UNPINNED_DEP",
            "NO_PYTHON_IN_STACK",
            "THIN_BEST_PRACTICES",
            "MISSING_HOW_TO_RUN",
            "FILE_PATH_NOT_IN_TOUCHED",
            "DUPLICATE_STEP_NUMBERS",
            "PATH_OUTSIDE_CONVENTION",
            "NO_CHECKPOINTS",
            "THIN_TRANSCRIPT",
            "WEAK_FINAL_CODE",
        }
    ]

    if not remaining:
        return tutorial, RepairResult(
            applied=True,
            summary=f"Applied {len(actions)} deterministic fix(es)",
            actions=actions,
            remaining_issues=[],
        )

    try:
        compact = tutorial_compact(tutorial, max_code_chars=2000)
        findings_txt = "\n".join(
            f"- [{f.severity}] {f.code} @ {f.location}: {f.message} → {f.suggestion}"
            for f in remaining[:40]
        )
        system = """You are the Repair Agent for ProjectPalAI.
Return a COMPLETE ProjectTutorial JSON (snake_case).

Required:
- title, problem_statement, end_state, how_to_run (strings)
- estimated_hours MUST be a single number (float), never a list/tuple/range
- final_project_code MUST be a single STRING (not an object)

Each step.code MUST be either null or an OBJECT:
  {"language":"python","file_path":"src/....py","code":"...","explanation":"..."}
Never put raw code as a plain string in step.code.

Keep the same project topic. Fix structure and missing code. Modern Python 3.12+.
"""
        raw_dict = chat_json_dict(
            model=model,
            system=system,
            user=(
                f"FINDINGS TO FIX:\n{findings_txt}\n\n"
                f"CURRENT TUTORIAL (compact):\n{compact}\n\n"
                "Return the full corrected ProjectTutorial JSON."
            ),
            json_schema=ProjectTutorial.model_json_schema(),
            temperature=0.15,
            num_predict=16384,
            max_retries=2,
        )
        payload = normalize_tutorial_payload(raw_dict, fallback=tutorial)
        payload["estimated_hours"] = coerce_hours(
            payload.get("estimated_hours"), default=4.0
        )
        fixed = ProjectTutorial.model_validate(payload)
        fixed, extra = apply_deterministic_repairs(fixed, remaining)
        actions.extend(extra)
        actions.append(
            RepairAction(
                action="llm_full_repair",
                location="tutorial",
                detail=f"addressed {len(remaining)} remaining finding(s)",
            )
        )
        return fixed, RepairResult(
            applied=True,
            summary=f"LLM + deterministic repair ({len(actions)} actions)",
            actions=actions,
            remaining_issues=[],
        )
    except Exception as e:
        _log(f"LLM repair failed, keeping deterministic fixes: {e}")
        return tutorial, RepairResult(
            applied=bool(actions),
            summary=(
                f"Deterministic only ({len(actions)} actions); "
                f"LLM repair failed"
            ),
            actions=actions,
            remaining_issues=[f"{f.code}: {f.message}" for f in remaining[:20]],
        )