"""
ProjectPalAI — Pydantic schemas for project tutorials.

One product, linear build steps. Coerces common LLM shape mistakes.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


Difficulty = Literal["beginner", "intermediate", "advanced"]
ProjectSize = Literal["small", "medium", "monolithic"]


def _as_str(v: Any, *, default: str = "") -> str:
    if v is None:
        return default
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, dict):
        parts: List[str] = []
        for k, val in v.items():
            body = (
                val
                if isinstance(val, str)
                else json.dumps(val, indent=2, ensure_ascii=False)
            )
            parts.append(f"# --- {k} ---\n{body}")
        return "\n\n".join(parts) if parts else default
    if isinstance(v, list):
        return "\n".join(_as_str(x) for x in v if x is not None)
    return str(v)


def _as_str_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, list):
        out: List[str] = []
        for item in v:
            if item is None:
                continue
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                for key in ("path", "file", "name", "item", "text", "value"):
                    if key in item and item[key] is not None:
                        out.append(str(item[key]))
                        break
                else:
                    out.append(json.dumps(item, ensure_ascii=False))
            else:
                out.append(str(item))
        return out
    return [str(v)]


def coerce_hours(v: Any, default: float = 4.0) -> float:
    """
    Safe float for estimated_hours.
    Handles int/float/str/"2-4"/(2.0, 4.0)/[2, 4]/dict.
    NEVER calls float() on a tuple or list.
    """
    try:
        default_f = float(default) if not isinstance(default, (list, tuple)) else 4.0
    except Exception:
        default_f = 4.0

    if v is None or v == "":
        return max(0.5, default_f)

    # Critical path: range from LLM or old SIZE_TARGETS
    if isinstance(v, (list, tuple)):
        for item in v:
            if isinstance(item, (list, tuple)):
                continue
            try:
                return max(0.5, float(item))
            except Exception:
                continue
        return max(0.5, default_f)

    if isinstance(v, bool):
        return max(0.5, default_f)

    if isinstance(v, (int, float)):
        return max(0.5, float(v))

    if isinstance(v, dict):
        for key in ("hours", "value", "estimate", "estimated_hours", "min", "max"):
            if key in v and v[key] is not None:
                return coerce_hours(v[key], default=default_f)
        return max(0.5, default_f)

    if isinstance(v, str):
        s = v.strip().lower().replace("hours", "").replace("hrs", "").strip()
        for sep in ("–", "—", "-", " to "):
            if sep in s:
                s = s.split(sep, 1)[0].strip()
                break
        try:
            return max(0.5, float(s))
        except Exception:
            m = re.search(r"(\d+(?:\.\d+)?)", s)
            if m:
                return max(0.5, float(m.group(1)))
            return max(0.5, default_f)

    return max(0.5, default_f)


def _guess_path_from_code(body: str, default: str = "src/main.py") -> str:
    for line in (body or "").lstrip().splitlines()[:4]:
        line = line.strip()
        if line.startswith("#") and ("." in line or "/" in line):
            token = line.lstrip("#").strip().split()[0].strip("()`'\"")
            if any(
                token.endswith(ext) for ext in (".py", ".toml", ".md", ".txt", ".cfg")
            ) or "/" in token:
                return token
    return default


class StackPackage(BaseModel):
    name: str = Field(description="Package or tool name")
    version: str = Field(description="Version pin, e.g. >=0.115")
    purpose: str = Field(default="", description="Why this dependency is used")

    @field_validator("name", "version", "purpose", mode="before")
    @classmethod
    def _str_fields(cls, v: Any) -> str:
        return _as_str(v, default="")


class CodeBlock(BaseModel):
    language: Literal["python"] = "python"
    file_path: str
    code: str
    explanation: str = ""
    expected_output: Optional[str] = None
    best_practice_notes: Optional[str] = None

    @field_validator("file_path", "code", "explanation", mode="before")
    @classmethod
    def _req_str(cls, v: Any) -> str:
        return _as_str(v, default="")

    @field_validator("expected_output", "best_practice_notes", mode="before")
    @classmethod
    def _opt_str(cls, v: Any) -> Optional[str]:
        if v is None or v == "":
            return None
        return _as_str(v)

    @field_validator("language", mode="before")
    @classmethod
    def _lang(cls, v: Any) -> str:
        return "python"


class BuildStep(BaseModel):
    step_number: int = Field(ge=1)
    title: str
    goal: str
    bullets: List[str] = Field(default_factory=list)
    speaker_notes: str
    code: Optional[CodeBlock] = None
    files_touched: List[str] = Field(default_factory=list)
    is_checkpoint: bool = False

    @field_validator("step_number", mode="before")
    @classmethod
    def _step_num(cls, v: Any) -> int:
        if isinstance(v, (list, tuple)):
            v = v[0] if v else 1
        try:
            return max(1, int(v))
        except Exception:
            return 1

    @field_validator("title", "goal", "speaker_notes", mode="before")
    @classmethod
    def _str_fields(cls, v: Any) -> str:
        return _as_str(v, default="")

    @field_validator("bullets", "files_touched", mode="before")
    @classmethod
    def _lists(cls, v: Any) -> List[str]:
        return _as_str_list(v)

    @field_validator("is_checkpoint", mode="before")
    @classmethod
    def _boolish(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(v)

    @field_validator("code", mode="before")
    @classmethod
    def _code_block(cls, v: Any) -> Any:
        if v is None or v == "" or v is False:
            return None
        if isinstance(v, str):
            body = v
            if body.strip().startswith("```"):
                lines = body.strip().splitlines()
                if lines and lines.startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                body = "\n".join(lines)
            return {
                "language": "python",
                "file_path": _guess_path_from_code(body),
                "code": body,
                "explanation": "",
            }
        if isinstance(v, dict):
            d = dict(v)
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
                d["code"] = _as_str(d["code"])
            d.setdefault("language", "python")
            d.setdefault(
                "file_path",
                _guess_path_from_code(str(d.get("code") or "")),
            )
            d.setdefault("code", "")
            d.setdefault("explanation", "")
            return d
        return v


class Challenge(BaseModel):
    title: str
    description: str
    build_process: str = ""
    solution_code: str = ""
    solution_walkthrough: str = ""
    sample_output: Optional[str] = None

    @field_validator(
        "title",
        "description",
        "build_process",
        "solution_code",
        "solution_walkthrough",
        mode="before",
    )
    @classmethod
    def _str_fields(cls, v: Any) -> str:
        return _as_str(v, default="")

    @field_validator("sample_output", mode="before")
    @classmethod
    def _opt_str(cls, v: Any) -> Optional[str]:
        if v is None or v == "":
            return None
        return _as_str(v)

    @model_validator(mode="before")
    @classmethod
    def _fill_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if not d.get("description"):
            for k in ("prompt", "task", "summary", "brief"):
                if d.get(k):
                    d["description"] = d[k]
                    break
        if not d.get("build_process"):
            for k in (
                "process",
                "guide",
                "approach",
                "instructions",
                "how_to_build",
                "build_guide",
                "steps",
                "hint",
            ):
                if d.get(k):
                    d["build_process"] = _as_str(d[k])
                    break
            else:
                d["build_process"] = _as_str(
                    d.get("description") or d.get("title") or "Extend the project."
                )
        if not d.get("solution_walkthrough"):
            for k in ("walkthrough", "solution", "explanation", "solution_notes"):
                if d.get(k) and k != "solution_code":
                    d["solution_walkthrough"] = _as_str(d[k])
                    break
            else:
                d.setdefault("solution_walkthrough", "")
        if not d.get("solution_code"):
            for k in ("code", "solution", "reference_code"):
                if isinstance(d.get(k), str) and k != "solution_walkthrough":
                    d["solution_code"] = d[k]
                    break
            else:
                d.setdefault("solution_code", "")
        d.setdefault("title", "Challenge")
        d.setdefault("description", d.get("title") or "Stretch goal")
        return d


class ProjectTutorial(BaseModel):
    id: str = ""
    title: str
    tagline: str = ""
    description: str = ""
    difficulty: Difficulty = "intermediate"
    size: ProjectSize = "medium"
    estimated_hours: float = Field(default=4.0, ge=0.5)

    problem_statement: str = ""
    end_state: str = ""
    prerequisites: List[str] = Field(default_factory=list)
    learning_outcomes: List[str] = Field(default_factory=list)
    repo_layout: List[str] = Field(default_factory=list)
    stack: List[StackPackage] = Field(default_factory=list)
    best_practices: List[str] = Field(default_factory=list)

    intro_transcript: str = ""
    steps: List[BuildStep] = Field(default_factory=list)
    outro_transcript: str = ""

    final_project_code: str = ""
    how_to_run: str = ""
    challenges: List[Challenge] = Field(default_factory=list)
    quality_report: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_hours_early(cls, data: Any) -> Any:
        """Run before field validation so float(tuple) never happens."""
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "estimated_hours" in d:
            d["estimated_hours"] = coerce_hours(d.get("estimated_hours"), default=4.0)
        return d

    @field_validator(
        "id",
        "title",
        "tagline",
        "description",
        "problem_statement",
        "end_state",
        "intro_transcript",
        "outro_transcript",
        "how_to_run",
        mode="before",
    )
    @classmethod
    def _str_fields(cls, v: Any) -> str:
        return _as_str(v, default="")

    @field_validator("final_project_code", mode="before")
    @classmethod
    def _final_code(cls, v: Any) -> str:
        return _as_str(v, default="")

    @field_validator(
        "prerequisites",
        "learning_outcomes",
        "repo_layout",
        "best_practices",
        mode="before",
    )
    @classmethod
    def _str_lists(cls, v: Any) -> List[str]:
        return _as_str_list(v)

    @field_validator("estimated_hours", mode="before")
    @classmethod
    def _hours(cls, v: Any) -> float:
        return coerce_hours(v, default=4.0)

    @field_validator("difficulty", mode="before")
    @classmethod
    def _diff(cls, v: Any) -> str:
        s = _as_str(v, default="intermediate").lower().strip()
        if s in ("beginner", "intermediate", "advanced"):
            return s
        return "intermediate"

    @field_validator("size", mode="before")
    @classmethod
    def _size(cls, v: Any) -> str:
        s = _as_str(v, default="medium").lower().strip()
        if s in ("small", "medium", "monolithic"):
            return s
        if s in ("large", "big", "full"):
            return "monolithic"
        return "medium"

    @field_validator("stack", mode="before")
    @classmethod
    def _stack(cls, v: Any) -> list:
        if v is None or not isinstance(v, list):
            return []
        out = []
        for item in v:
            if isinstance(item, str):
                name, ver = item, ">=0.1"
                for sep in (">=", "==", "~=", ">"):
                    if sep in item:
                        name, ver = item.split(sep, 1)
                        ver = sep + ver
                        break
                out.append({"name": name.strip(), "version": ver, "purpose": ""})
            elif isinstance(item, dict):
                d = dict(item)
                d.setdefault("name", d.get("package") or d.get("lib") or "package")
                d.setdefault("version", d.get("ver") or ">=1.0")
                d.setdefault("purpose", d.get("why") or d.get("use") or "")
                out.append(d)
        return out

    @field_validator("steps", mode="before")
    @classmethod
    def _steps(cls, v: Any) -> list:
        if v is None:
            return []
        return list(v) if isinstance(v, list) else []

    @field_validator("challenges", mode="before")
    @classmethod
    def _challenges(cls, v: Any) -> list:
        if v is None or not isinstance(v, list):
            return []
        return [c for c in v if isinstance(c, (dict, Challenge))]

    @field_validator("quality_report", mode="before")
    @classmethod
    def _qr(cls, v: Any) -> Any:
        if v is None or v == "":
            return None
        return v if isinstance(v, dict) else None


Course = ProjectTutorial
Slide = BuildStep
Module = BuildStep