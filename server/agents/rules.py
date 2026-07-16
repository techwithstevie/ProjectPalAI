"""Deterministic checks (no LLM) for structure, practices, and code."""
from __future__ import annotations

import re
from typing import Any, List

from .models import AgentReview, Finding

LEGACY_PATTERNS = [
    (r"\bprint\s+[^(]", "Bare print statement (prefer functions / logging)"),
    (r"from sklearn\.cross_validation\b", "Deprecated sklearn.cross_validation"),
    (r"\btf\.Session\b", "Legacy TensorFlow Session API"),
    (r"\bpip install sklearn\b", "Use scikit-learn package name, pin versions"),
    (r"except\s*:", "Bare except is bad practice"),
    (r"\bexec\s*\(", "Avoid exec in teaching demos"),
    (r"\beval\s*\(", "Avoid eval in teaching demos"),
]

REQUIRED_LAYOUT_HINTS = ["src", "tests", "pyproject.toml", "README"]


def _dump(tutorial: Any) -> dict:
    return tutorial.model_dump() if hasattr(tutorial, "model_dump") else dict(tutorial)


def run_structure_rules(tutorial: Any) -> AgentReview:
    data = _dump(tutorial)
    findings: List[Finding] = []

    layout = [str(x) for x in (data.get("repo_layout") or [])]
    layout_join = " ".join(layout).lower()

    for hint in REQUIRED_LAYOUT_HINTS:
        if hint.lower() not in layout_join:
            findings.append(
                Finding(
                    agent="structure",
                    severity="error",
                    code="MISSING_LAYOUT_ENTRY",
                    message=f"repo_layout should include something like '{hint}'",
                    location="repo_layout",
                    suggestion=f"Add '{hint}' (or '{hint}/') to repo_layout",
                )
            )

    for i, step in enumerate(data.get("steps") or []):
        code = step.get("code")
        if isinstance(code, dict) and code.get("file_path"):
            fp = str(code["file_path"]).replace("\\", "/")
            if fp.startswith("/") or ".." in fp.split("/"):
                findings.append(
                    Finding(
                        agent="structure",
                        severity="error",
                        code="UNSAFE_PATH",
                        message=f"Unsafe or absolute path: {fp}",
                        location=f"steps[{i}].code.file_path",
                        suggestion="Use relative project paths like src/module.py",
                    )
                )
            if not (
                fp.startswith("src/")
                or fp.startswith("tests/")
                or fp in ("pyproject.toml", "README.md", "main.py")
                or fp.startswith("scripts/")
            ):
                findings.append(
                    Finding(
                        agent="structure",
                        severity="warning",
                        code="PATH_OUTSIDE_CONVENTION",
                        message=f"Path '{fp}' is outside src/, tests/, or root config",
                        location=f"steps[{i}].code.file_path",
                        suggestion="Prefer src/... or tests/...",
                    )
                )

        for ft in step.get("files_touched") or []:
            ft = str(ft).replace("\\", "/")
            if not ft.endswith("/") and "." not in ft.split("/")[-1]:
                findings.append(
                    Finding(
                        agent="structure",
                        severity="info",
                        code="DIR_ONLY_TOUCH",
                        message=f"files_touched lists directory-like path: {ft}",
                        location=f"steps[{i}].files_touched",
                    )
                )

    for i, step in enumerate(data.get("steps") or []):
        code = step.get("code")
        if not isinstance(code, dict) or not code.get("file_path"):
            continue
        fp = str(code["file_path"])
        touched = [str(x) for x in (step.get("files_touched") or [])]
        if touched and fp not in touched:
            findings.append(
                Finding(
                    agent="structure",
                    severity="warning",
                    code="FILE_PATH_NOT_IN_TOUCHED",
                    message=f"code.file_path '{fp}' missing from files_touched",
                    location=f"steps[{i}]",
                    suggestion=f"Add '{fp}' to files_touched",
                )
            )

    nums = [s.get("step_number") for s in (data.get("steps") or [])]
    if len(nums) != len(set(nums)):
        findings.append(
            Finding(
                agent="structure",
                severity="error",
                code="DUPLICATE_STEP_NUMBERS",
                message="Duplicate step_number values",
                location="steps",
                suggestion="Renumber steps sequentially from 1",
            )
        )

    errors = [f for f in findings if f.severity == "error"]
    return AgentReview(
        agent="structure",
        passed=len(errors) == 0,
        summary=(
            "Structure OK"
            if not findings
            else f"{len(findings)} structure finding(s), {len(errors)} error(s)"
        ),
        findings=findings,
    )


def run_practices_rules(tutorial: Any) -> AgentReview:
    data = _dump(tutorial)
    findings: List[Finding] = []

    stack = data.get("stack") or []
    if not stack:
        findings.append(
            Finding(
                agent="practices",
                severity="error",
                code="EMPTY_STACK",
                message="stack is empty",
                location="stack",
                suggestion="Pin modern packages with versions and purposes",
            )
        )
    else:
        for i, pkg in enumerate(stack):
            if not isinstance(pkg, dict):
                continue
            ver = str(pkg.get("version") or "").strip().lower()
            if ver in ("", "latest", "*"):
                findings.append(
                    Finding(
                        agent="practices",
                        severity="warning",
                        code="UNPINNED_DEP",
                        message=(
                            f"Package '{pkg.get('name')}' has weak version pin: "
                            f"{ver or '(empty)'}"
                        ),
                        location=f"stack[{i}]",
                        suggestion="Use a modern lower bound e.g. >=2.2 or >=1.5",
                    )
                )
        names = {
            str(p.get("name", "")).lower()
            for p in stack
            if isinstance(p, dict)
        }
        if "python" not in names and "python3" not in names:
            findings.append(
                Finding(
                    agent="practices",
                    severity="info",
                    code="NO_PYTHON_IN_STACK",
                    message="stack does not list python runtime",
                    location="stack",
                    suggestion="Include python >=3.12",
                )
            )

    practices = data.get("best_practices") or []
    if len(practices) < 3:
        findings.append(
            Finding(
                agent="practices",
                severity="warning",
                code="THIN_BEST_PRACTICES",
                message="best_practices list is thin",
                location="best_practices",
                suggestion="Document type hints, src layout, tests, reproducibility",
            )
        )

    how = str(data.get("how_to_run") or "")
    if len(how.strip()) < 10:
        findings.append(
            Finding(
                agent="practices",
                severity="error",
                code="MISSING_HOW_TO_RUN",
                message="how_to_run is missing or too short",
                location="how_to_run",
                suggestion="Document install + run commands",
            )
        )

    for i, step in enumerate(data.get("steps") or []):
        code = step.get("code")
        if not isinstance(code, dict):
            continue
        body = str(code.get("code") or "")
        for pat, msg in LEGACY_PATTERNS:
            if re.search(pat, body):
                findings.append(
                    Finding(
                        agent="practices",
                        severity="warning",
                        code="LEGACY_PATTERN",
                        message=msg,
                        location=f"steps[{i}].code",
                        suggestion="Rewrite with modern APIs",
                    )
                )
        if "def " in body and "->" not in body and len(body) > 120:
            findings.append(
                Finding(
                    agent="practices",
                    severity="info",
                    code="MISSING_RETURN_HINTS",
                    message="Functions may lack return type hints",
                    location=f"steps[{i}].code",
                    suggestion="Add -> return annotations",
                )
            )

    errors = [f for f in findings if f.severity == "error"]
    return AgentReview(
        agent="practices",
        passed=len(errors) == 0,
        summary=(
            "Practices OK"
            if not findings
            else f"{len(findings)} practices finding(s), {len(errors)} error(s)"
        ),
        findings=findings,
    )


def run_code_rules(tutorial: Any) -> AgentReview:
    data = _dump(tutorial)
    findings: List[Finding] = []
    steps = data.get("steps") or []

    if len(steps) < 3:
        findings.append(
            Finding(
                agent="code",
                severity="error",
                code="TOO_FEW_STEPS",
                message=f"Only {len(steps)} steps — tutorial too thin",
                location="steps",
            )
        )

    code_steps = 0
    checkpoints = 0
    for i, step in enumerate(steps):
        code = step.get("code")
        has_code = False
        if isinstance(code, dict) and str(code.get("code") or "").strip():
            has_code = True
        elif isinstance(code, str) and code.strip():
            has_code = True
        if has_code:
            code_steps += 1
            body = (
                str(code.get("code") or "")
                if isinstance(code, dict)
                else str(code)
            )
            if "TODO" in body or "pass  # implement" in body:
                findings.append(
                    Finding(
                        agent="code",
                        severity="warning",
                        code="STUB_CODE",
                        message="Code looks like a stub / TODO",
                        location=f"steps[{i}].code",
                        suggestion="Provide complete runnable code for the milestone",
                    )
                )
            if len(body.strip()) < 20:
                findings.append(
                    Finding(
                        agent="code",
                        severity="warning",
                        code="TINY_CODE",
                        message="Code block is very small",
                        location=f"steps[{i}].code",
                    )
                )
        if step.get("is_checkpoint"):
            checkpoints += 1

        notes = str(step.get("speaker_notes") or "")
        if len(notes.strip()) < 40:
            findings.append(
                Finding(
                    agent="code",
                    severity="warning",
                    code="THIN_TRANSCRIPT",
                    message="speaker_notes too short for a real tutorial step",
                    location=f"steps[{i}].speaker_notes",
                )
            )

    if steps and code_steps / max(len(steps), 1) < 0.5:
        findings.append(
            Finding(
                agent="code",
                severity="error",
                code="TOO_FEW_CODE_STEPS",
                message=f"Only {code_steps}/{len(steps)} steps include code",
                location="steps",
                suggestion="Most steps should ship code into the project",
            )
        )

    if len(steps) >= 6 and checkpoints == 0:
        findings.append(
            Finding(
                agent="code",
                severity="warning",
                code="NO_CHECKPOINTS",
                message="No checkpoint steps — learners never pause to run",
                location="steps",
                suggestion="Mark every few steps is_checkpoint=true",
            )
        )

    final = str(data.get("final_project_code") or "")
    if len(final.strip()) < 40:
        findings.append(
            Finding(
                agent="code",
                severity="warning",
                code="WEAK_FINAL_CODE",
                message="final_project_code is missing or weak",
                location="final_project_code",
            )
        )

    errors = [f for f in findings if f.severity == "error"]
    return AgentReview(
        agent="code",
        passed=len(errors) == 0,
        summary=(
            "Code structure OK"
            if not findings
            else f"{len(findings)} code finding(s), {len(errors)} error(s)"
        ),
        findings=findings,
    )