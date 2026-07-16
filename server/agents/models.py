"""Schemas for agent findings — tolerant of messy LLM JSON."""
from __future__ import annotations

import re
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Severity = Literal["info", "warning", "error"]
AgentName = Literal["structure", "practices", "code", "repair"]


def _as_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float, bool)):
        return str(v)
    return str(v)


def _safe_float(v: Any, default: float = 0.0) -> float:
    if isinstance(v, (list, tuple)):
        for item in v:
            try:
                return float(item)
            except Exception:
                continue
        return default
    if isinstance(v, bool):
        return default
    try:
        return float(v)
    except Exception:
        return default


def _slug_code(message: str, prefix: str = "FINDING") -> str:
    words = re.findall(r"[A-Za-z0-9]+", message or "")
    if not words:
        return prefix
    return "_".join(w.upper() for w in words[:4])[:48] or prefix


def _normalize_finding(item: Any, default_agent: str = "structure") -> dict:
    if isinstance(item, str):
        return {
            "agent": default_agent,
            "severity": "warning",
            "code": _slug_code(item),
            "message": item.strip() or "Issue noted",
            "location": "",
            "suggestion": "",
        }
    if not isinstance(item, dict):
        return {
            "agent": default_agent,
            "severity": "info",
            "code": "UNKNOWN",
            "message": _as_str(item) or "Issue noted",
            "location": "",
            "suggestion": "",
        }

    d = dict(item)
    agent = d.get("agent") or default_agent
    if agent not in ("structure", "practices", "code", "repair"):
        agent = default_agent

    severity = _as_str(d.get("severity") or d.get("level") or "warning").lower()
    if severity not in ("info", "warning", "error"):
        severity = "warning"

    message = _as_str(
        d.get("message")
        or d.get("detail")
        or d.get("description")
        or d.get("text")
        or d.get("issue")
        or ""
    )
    code = _as_str(d.get("code") or d.get("id") or d.get("rule") or "")
    if not code:
        code = _slug_code(message)

    location = _as_str(
        d.get("location") or d.get("path") or d.get("file") or d.get("where") or ""
    )
    suggestion = _as_str(
        d.get("suggestion") or d.get("fix") or d.get("recommendation") or ""
    )

    return {
        "agent": agent,
        "severity": severity,
        "code": code,
        "message": message or code,
        "location": location,
        "suggestion": suggestion,
    }


class Finding(BaseModel):
    agent: AgentName = "structure"
    severity: Severity = "warning"
    code: str = Field(default="FINDING")
    message: str = Field(default="")
    location: str = Field(default="")
    suggestion: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if isinstance(data, (str, dict)) or data is None:
            return _normalize_finding(data or {})
        return data


class AgentReview(BaseModel):
    agent: AgentName = "structure"
    passed: bool = True
    summary: str = Field(default="")
    findings: List[Finding] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {
                "agent": "structure",
                "passed": True,
                "summary": _as_str(data),
                "findings": [],
            }

        d = dict(data)
        agent = _as_str(d.get("agent") or "structure").lower()
        if agent not in ("structure", "practices", "code", "repair"):
            agent = "structure"
        d["agent"] = agent

        raw_findings = d.get("findings")
        if raw_findings is None:
            raw_findings = (
                d.get("issues")
                or d.get("problems")
                or d.get("notes")
                or d.get("results")
                or []
            )
        if isinstance(raw_findings, str):
            raw_findings = [raw_findings]
        if not isinstance(raw_findings, list):
            raw_findings = []
        d["findings"] = [
            _normalize_finding(f, default_agent=agent) for f in raw_findings
        ]

        if "passed" not in d or d.get("passed") is None:
            errors = [f for f in d["findings"] if f.get("severity") == "error"]
            d["passed"] = len(errors) == 0
        else:
            p = d["passed"]
            if isinstance(p, str):
                d["passed"] = p.strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "pass",
                    "ok",
                }
            else:
                d["passed"] = bool(p)

        if not d.get("summary"):
            n = len(d["findings"])
            errs = sum(1 for f in d["findings"] if f.get("severity") == "error")
            d["summary"] = (
                f"{agent} review OK"
                if n == 0
                else f"{agent}: {n} finding(s), {errs} error(s)"
            )
        else:
            d["summary"] = _as_str(d["summary"])

        return d


class RepairAction(BaseModel):
    action: str = Field(default="fix")
    location: str = Field(default="")
    detail: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"action": data, "location": "", "detail": ""}
        if not isinstance(data, dict):
            return {"action": _as_str(data), "location": "", "detail": ""}
        d = dict(data)
        return {
            "action": _as_str(
                d.get("action") or d.get("type") or d.get("name") or "fix"
            ),
            "location": _as_str(d.get("location") or d.get("path") or ""),
            "detail": _as_str(
                d.get("detail") or d.get("message") or d.get("description") or ""
            ),
        }


class RepairResult(BaseModel):
    applied: bool = False
    summary: str = Field(default="")
    actions: List[RepairAction] = Field(default_factory=list)
    remaining_issues: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {
                "applied": False,
                "summary": _as_str(data),
                "actions": [],
                "remaining_issues": [],
            }
        d = dict(data)
        d.setdefault("applied", bool(d.get("actions")))
        d.setdefault("summary", "")
        if not isinstance(d.get("actions"), list):
            d["actions"] = []
        if not isinstance(d.get("remaining_issues"), list):
            ri = d.get("remaining_issues")
            d["remaining_issues"] = [str(ri)] if ri else []
        d["remaining_issues"] = [str(x) for x in d["remaining_issues"]]
        return d


class QualityReport(BaseModel):
    passed: bool = True
    score: float = Field(default=100.0, ge=0, le=100)
    reviews: List[AgentReview] = Field(default_factory=list)
    repair: Optional[RepairResult] = None
    findings_count: int = 0
    error_count: int = 0
    warning_count: int = 0

    @field_validator("score", mode="before")
    @classmethod
    def _score(cls, v: Any) -> float:
        s = _safe_float(v, default=100.0)
        return max(0.0, min(100.0, s))

    @field_validator("findings_count", "error_count", "warning_count", mode="before")
    @classmethod
    def _counts(cls, v: Any) -> int:
        if isinstance(v, (list, tuple)):
            return len(v)
        try:
            return int(v)
        except Exception:
            return 0