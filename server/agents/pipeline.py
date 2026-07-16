"""Orchestrate structure → practices → code → repair."""
from __future__ import annotations

from typing import Callable

from schema import ProjectTutorial, coerce_hours

from .code_agent import review_code
from .models import QualityReport
from .practices_agent import review_practices
from .repair_agent import repair_with_llm
from .structure_agent import review_structure


def _score(error_count: int, warning_count: int, total: int) -> float:
    try:
        e = int(error_count) if not isinstance(error_count, (list, tuple)) else 0
        w = int(warning_count) if not isinstance(warning_count, (list, tuple)) else 0
        t = int(total) if total and not isinstance(total, (list, tuple)) else 1
    except Exception:
        return 100.0
    if t <= 0:
        return 100.0
    penalty = e * 12 + w * 4
    return float(max(0, min(100, 100 - penalty)))


def run_quality_pipeline(
    tutorial: ProjectTutorial,
    *,
    model: str = "gpt-oss:120b-cloud",
    use_llm_review: bool = True,
    use_llm_repair: bool = True,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[ProjectTutorial, QualityReport]:
    def log(msg: str):
        print(f"[quality] {msg}")
        if progress_callback:
            progress_callback(msg)

    # Guard hours before any agent work
    tutorial.estimated_hours = coerce_hours(tutorial.estimated_hours, default=4.0)

    log("Agent 1/3 — Structure review…")
    r_struct = review_structure(
        tutorial, model=model, use_llm=use_llm_review, log=log
    )

    log("Agent 2/3 — Best practices review…")
    r_prac = review_practices(
        tutorial, model=model, use_llm=use_llm_review, log=log
    )

    log("Agent 3/3 — Code quality review…")
    r_code = review_code(
        tutorial, model=model, use_llm=use_llm_review, log=log
    )

    reviews = [r_struct, r_prac, r_code]
    all_findings = [f for r in reviews for f in r.findings]
    errors = [f for f in all_findings if f.severity == "error"]
    warnings = [f for f in all_findings if f.severity == "warning"]

    log(
        f"Review complete: {len(all_findings)} finding(s) "
        f"({len(errors)} errors, {len(warnings)} warnings)"
    )

    repair_result = None
    final = tutorial

    if all_findings:
        log("Repair agent — applying fixes…")
        if use_llm_repair:
            final, repair_result = repair_with_llm(
                tutorial, all_findings, model=model, log=log
            )
        else:
            from .models import RepairResult
            from .repair_agent import apply_deterministic_repairs

            final, actions = apply_deterministic_repairs(tutorial, all_findings)
            repair_result = RepairResult(
                applied=bool(actions),
                summary=f"Deterministic repair ({len(actions)} actions)",
                actions=actions,
                remaining_issues=[],
            )

        final.estimated_hours = coerce_hours(final.estimated_hours, default=4.0)

        log("Re-validating after repair…")
        r_struct2 = review_structure(
            final, model=model, use_llm=False, log=log
        )
        r_prac2 = review_practices(
            final, model=model, use_llm=False, log=log
        )
        r_code2 = review_code(final, model=model, use_llm=False, log=log)
        reviews = [r_struct2, r_prac2, r_code2]
        all_findings = [f for r in reviews for f in r.findings]
        errors = [f for f in all_findings if f.severity == "error"]
        warnings = [f for f in all_findings if f.severity == "warning"]

    score = _score(len(errors), len(warnings), max(len(all_findings), 1))
    passed = len(errors) == 0

    report = QualityReport(
        passed=passed,
        score=score,
        reviews=reviews,
        repair=repair_result,
        findings_count=len(all_findings),
        error_count=len(errors),
        warning_count=len(warnings),
    )

    final.estimated_hours = coerce_hours(final.estimated_hours, default=4.0)

    try:
        final.quality_report = report.model_dump()
    except Exception:
        pass

    log(
        f"Quality pipeline done — score {score:.0f}/100 "
        f"({'pass' if passed else 'issues remain'})"
    )
    return final, report