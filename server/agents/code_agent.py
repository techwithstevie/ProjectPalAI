"""Code agent: step code quality, coverage, checkpoints, transcripts."""
from __future__ import annotations

from typing import Any, Callable

from .llm import chat_structured, tutorial_compact
from .models import AgentReview
from .rules import run_code_rules

SYSTEM = """You are the Code Quality Agent for ProjectPalAI.
Tutorials must teach by building: most steps ship real code into the same project.
Check:
- Enough steps with real (non-stub) code
- file_path consistency with progressive project
- Checkpoints present on longer tutorials
- Transcripts long enough to teach the build
- final_project_code and how_to_run present

Return JSON matching AgentReview with agent='code'.
Each finding MUST be an object with:
  agent, severity, code, message, location, suggestion
Never put findings as plain strings.
Findings only — do not rewrite the tutorial.
"""


def review_code(
    tutorial: Any,
    *,
    model: str,
    use_llm: bool = True,
    log: Callable[[str], None] | None = None,
) -> AgentReview:
    def _log(m: str):
        if log:
            log(m)

    base = run_code_rules(tutorial)
    _log(f"Code rules: {base.summary}")

    if not use_llm:
        return base

    try:
        compact = tutorial_compact(tutorial, max_code_chars=800)
        llm_review = chat_structured(
            model=model,
            system=SYSTEM,
            user=(
                "Audit code quality and build progression.\n"
                f"{compact}\n\n"
                "Return AgentReview with agent='code'."
            ),
            schema=AgentReview,
            temperature=0.05,
            num_predict=4096,
        )
        llm_review.agent = "code"
        seen = {(f.code, f.location, f.message) for f in base.findings}
        merged = list(base.findings)
        for f in llm_review.findings:
            f.agent = "code"
            key = (f.code, f.location, f.message)
            if key not in seen:
                merged.append(f)
                seen.add(key)
        errors = [f for f in merged if f.severity == "error"]
        return AgentReview(
            agent="code",
            passed=len(errors) == 0,
            summary=f"Code: {len(merged)} finding(s), {len(errors)} error(s)",
            findings=merged,
        )
    except Exception as e:
        _log(f"Code LLM skipped: {e}")
        return base