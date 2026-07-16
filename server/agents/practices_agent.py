"""Best-practices agent: modern stack, APIs, teaching hygiene."""
from __future__ import annotations

from typing import Any, Callable

from .llm import chat_structured, tutorial_compact
from .models import AgentReview
from .rules import run_practices_rules

SYSTEM = """You are the Best Practices Agent for ProjectPalAI.
Ensure tutorials teach modern engineering:
- Python 3.12+, type hints, pathlib, pyproject.toml
- Pinned dependency versions (not 'latest')
- src layout, tests
- Prefer Pipeline/composition; no deprecated sklearn/TF APIs
- No bare except, eval/exec; clear entrypoints
- how_to_run must be real commands

Return JSON matching AgentReview with agent='practices'.
Each finding needs: agent, severity, code, message, location, suggestion.
passed=false if any error-level issues.
Do not rewrite the full tutorial — findings only.
"""


def review_practices(
    tutorial: Any,
    *,
    model: str,
    use_llm: bool = True,
    log: Callable[[str], None] | None = None,
) -> AgentReview:
    def _log(m: str):
        if log:
            log(m)

    base = run_practices_rules(tutorial)
    _log(f"Practices rules: {base.summary}")

    if not use_llm:
        return base

    try:
        compact = tutorial_compact(tutorial)
        llm_review = chat_structured(
            model=model,
            system=SYSTEM,
            user=(
                "Audit best practices for this tutorial.\n"
                f"{compact}\n\n"
                "Return AgentReview with agent='practices'."
            ),
            schema=AgentReview,
            temperature=0.05,
            num_predict=4096,
        )
        llm_review.agent = "practices"
        seen = {(f.code, f.location, f.message) for f in base.findings}
        merged = list(base.findings)
        for f in llm_review.findings:
            f.agent = "practices"
            key = (f.code, f.location, f.message)
            if key not in seen:
                merged.append(f)
                seen.add(key)
        errors = [f for f in merged if f.severity == "error"]
        return AgentReview(
            agent="practices",
            passed=len(errors) == 0,
            summary=f"Practices: {len(merged)} finding(s), {len(errors)} error(s)",
            findings=merged,
        )
    except Exception as e:
        _log(f"Practices LLM skipped: {e}")
        return base