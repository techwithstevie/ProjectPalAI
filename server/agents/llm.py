"""Shared Ollama helpers for agents — local server only, tolerant JSON parse."""
from __future__ import annotations

import json
import re
from typing import Any, Type, TypeVar

import ollama
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

HARMONY_CHANNEL = re.compile(
    r"<\|channel\|>\s*analysis\s*<\|message\|>.*?(?:<\|end\|>|<\|start\|>)",
    re.DOTALL,
)
HARMONY_FINAL = re.compile(r"<\|channel\|>\s*final\s*<\|message\|>", re.IGNORECASE)
HARMONY_TAGS = re.compile(r"<\|[a-z_]+\|>", re.IGNORECASE)


def _strip_harmony(raw: str) -> str:
    raw = HARMONY_CHANNEL.sub("", raw)
    m = HARMONY_FINAL.search(raw)
    if m:
        raw = raw[m.end() :]
    return HARMONY_TAGS.sub("", raw).strip()


def extract_json(raw: str) -> str:
    raw = _strip_harmony(raw or "")
    if not raw.strip():
        return "{}"
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fence:
        return fence.group(1)
    start_obj, end_obj = raw.find("{"), raw.rfind("}")
    start_arr, end_arr = raw.find("["), raw.rfind("]")
    if start_obj != -1 and end_obj > start_obj:
        return raw[start_obj : end_obj + 1]
    if start_arr != -1 and end_arr > start_arr:
        try:
            return json.dumps({"findings": json.loads(raw[start_arr : end_arr + 1])})
        except Exception:
            pass
    return raw


def chat_structured(
    *,
    model: str,
    system: str,
    user: str,
    schema: Type[T],
    temperature: float = 0.1,
    num_predict: int = 8192,
    max_retries: int = 2,
) -> T:
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            kwargs: dict = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": schema.model_json_schema(),
                "options": {
                    "temperature": temperature,
                    "num_predict": num_predict,
                },
            }
            try:
                response = ollama.chat(**kwargs, think=False)
            except TypeError:
                response = ollama.chat(**kwargs)

            raw = response["message"]["content"]
            if not str(raw).strip():
                raise ValueError("Empty model response")

            parsed = json.loads(extract_json(str(raw)))
            if isinstance(parsed, list):
                parsed = {
                    "findings": parsed,
                    "passed": False,
                    "summary": "LLM findings list",
                }
            if not isinstance(parsed, dict):
                parsed = {
                    "summary": str(parsed),
                    "findings": [],
                    "passed": True,
                }

            return schema.model_validate(parsed)
        except Exception as e:
            last_err = e
            print(f"[agents.llm] attempt {attempt + 1} failed: {e}")
    raise RuntimeError(f"Agent structured chat failed: {last_err}")


def chat_json_dict(
    *,
    model: str,
    system: str,
    user: str,
    json_schema: dict | None = None,
    temperature: float = 0.1,
    num_predict: int = 8192,
    max_retries: int = 2,
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
            if json_schema is not None:
                kwargs["format"] = json_schema
            else:
                kwargs["format"] = "json"
            try:
                response = ollama.chat(**kwargs, think=False)
            except TypeError:
                response = ollama.chat(**kwargs)
            raw = response["message"]["content"]
            if not str(raw).strip():
                raise ValueError("Empty model response")
            parsed = json.loads(extract_json(str(raw)))
            if isinstance(parsed, list):
                return {"findings": parsed}
            if not isinstance(parsed, dict):
                return {"value": parsed}
            return parsed
        except Exception as e:
            last_err = e
            print(f"[agents.llm] chat_json_dict attempt {attempt + 1} failed: {e}")
    raise RuntimeError(f"Agent json chat failed: {last_err}")


def tutorial_compact(tutorial: Any, max_code_chars: int = 1200) -> dict:
    if hasattr(tutorial, "model_dump"):
        data = tutorial.model_dump()
    else:
        data = dict(tutorial)

    steps = []
    for s in data.get("steps") or []:
        code = s.get("code")
        code_snip = None
        if isinstance(code, dict) and code.get("code"):
            body = str(code["code"])
            if len(body) > max_code_chars:
                body = body[:max_code_chars] + "\n# ... truncated ..."
            code_snip = {
                "file_path": code.get("file_path"),
                "code": body,
                "explanation": (code.get("explanation") or "")[:200],
            }
        elif isinstance(code, str) and code.strip():
            body = (
                code
                if len(code) <= max_code_chars
                else code[:max_code_chars] + "\n# ..."
            )
            code_snip = {
                "file_path": "src/main.py",
                "code": body,
                "explanation": "",
            }
        steps.append(
            {
                "step_number": s.get("step_number"),
                "title": s.get("title"),
                "goal": s.get("goal"),
                "files_touched": s.get("files_touched"),
                "is_checkpoint": s.get("is_checkpoint"),
                "bullets": (s.get("bullets") or [])[:6],
                "code": code_snip,
            }
        )

    fpc = data.get("final_project_code")
    if not isinstance(fpc, str):
        fpc = str(fpc or "")

    return {
        "title": data.get("title"),
        "difficulty": data.get("difficulty"),
        "size": data.get("size"),
        "problem_statement": data.get("problem_statement"),
        "end_state": data.get("end_state"),
        "repo_layout": data.get("repo_layout"),
        "stack": data.get("stack"),
        "best_practices": data.get("best_practices"),
        "prerequisites": data.get("prerequisites"),
        "learning_outcomes": data.get("learning_outcomes"),
        "how_to_run": data.get("how_to_run"),
        "final_project_code": fpc[:max_code_chars],
        "steps": steps,
        "challenges_count": len(data.get("challenges") or []),
    }