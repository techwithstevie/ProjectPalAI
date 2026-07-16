"""Structure agent: deterministic rules + optional LLM deep pass."""
from __future__ import annotations

from typing import Any, Callable

from .llm import chat_structured, tutorial_compact
from .models import AgentReview
from .rules import run_structure_rules

SYSTEM = """You are the Structure Agent for ProjectPalAI.
Review project tutorials for correct file/folder structure only.
Focus on: src/ layout, tests/, pyproject.toml, consistent file_path values,
no absolute paths, sequential steps, files_touched alignment.

Return JSON matching AgentReview:
{
  "agent": "structure",
  "passed": true/false,
  "summary": "short string",
  "findings": [
    {
      "agent": "structure",
      "severity": "info|warning|error",
      "code": "MACHINE_CODE",
      "message": "what is wrong",
      "location": "where",
      "suggestion": "how to fix"
    }
  ]
}
passed=false if any error-level issues remain.
Do not rewrite code — only report findings.
"""


def review_structure(
    tutorial: Any,
    *,
    model: str,
    use_llm: bool = True,
    log: Callable[[str], None] | None = None,
) -> AgentReview:
    def _log(m: str):
        if log:
            log(m)

    base = run_structure_rules(tutorial)
    _log(f"Structure rules: {base.summary}")

    if not use_llm:
        return base

    try:
        compact = tutorial_compact(tutorial)
        llm_review = chat_structured(
            model=model,
            system=SYSTEM,
            user=(
                "Review this ProjectPalAI tutorial structure.\n"
                f"{compact}\n\n"
                "Return AgentReview with agent='structure'."
            ),
            schema=AgentReview,
            temperature=0.05,
            num_predict=4096,
        )
        llm_review.agent = "structure"
        seen = {(f.code, f.location, f.message) for f in base.findings}
        merged = list(base.findings)
        for f in llm_review.findings:
            f.agent = "structure"
            key = (f.code, f.location, f.message)
            if key not in seen:
                merged.append(f)
                seen.add(key)
        errors = [f for f in merged if f.severity == "error"]
        return AgentReview(
            agent="structure",
            passed=len(errors) == 0,
            summary=f"Structure: {len(merged)} finding(s), {len(errors)} error(s)",
            findings=merged,
        )
    except Exception as e:
        _log(f"Structure LLM skipped: {e}")
        return base