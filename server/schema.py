"""
Teachly — YouTube-style project tutorial schema.

One project. Linear build steps. No modules, no charts.
Learn only by building.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

Difficulty = Literal["beginner", "intermediate", "advanced"]
ProjectSize = Literal["small", "medium", "monolithic"]


class StackPackage(BaseModel):
    name: str
    version: str = Field(description="Modern pin, e.g. >=2.2")
    purpose: str


class CodeBlock(BaseModel):
    language: Literal["python"] = "python"
    file_path: str = Field(
        default="src/main.py",
        description="Where this code belongs in the project",
    )
    code: str = Field(description="Complete, runnable code for this step")
    explanation: str = Field(
        description="What this code does in the project"
    )
    expected_output: str = ""
    best_practice_notes: str = ""


class BuildStep(BaseModel):
    """One chapter of the tutorial — like a YouTube section."""
    step_number: int
    title: str
    goal: str = Field(
        description="What the project can do after this step"
    )
    bullets: List[str] = Field(
        description="4-8 short on-screen points (viewer-facing)"
    )
    speaker_notes: str = Field(
        description=(
            "FULL spoken transcript for this step — YouTube-tutorial style. "
            "Walk through building and running the code (~300-600 words). "
            "Not a bullet restatement."
        )
    )
    code: Optional[CodeBlock] = None
    files_touched: List[str] = Field(default_factory=list)
    is_checkpoint: bool = Field(
        default=False,
        description="True if student should pause and run/test here",
    )


class Challenge(BaseModel):
    """Optional stretch task after the main build."""
    title: str
    description: str
    build_process: str
    solution_code: str
    solution_walkthrough: str
    sample_output: str = ""


class ProjectTutorial(BaseModel):
    id: Optional[str] = None
    title: str
    tagline: str = ""
    description: str
    difficulty: Difficulty
    size: ProjectSize
    estimated_hours: float = Field(
        description="Rough completion time for the full build"
    )
    problem_statement: str
    end_state: str = Field(
        description="What the finished project does"
    )
    prerequisites: List[str] = Field(default_factory=list)
    learning_outcomes: List[str] = Field(default_factory=list)
    repo_layout: List[str] = Field(default_factory=list)
    stack: List[StackPackage] = Field(default_factory=list)
    best_practices: List[str] = Field(default_factory=list)
    # Linear tutorial body
    intro_transcript: str = Field(
        default="",
        description="Opening monologue before step 1 (channel intro style)",
    )
    steps: List[BuildStep] = Field(
        description="Ordered build steps — the entire tutorial"
    )
    outro_transcript: str = Field(
        default="",
        description="Closing monologue after the last step",
    )
    final_project_code: str = Field(
        default="",
        description="Best-effort combined final source (instructor exemplar)",
    )
    how_to_run: str = Field(
        default="",
        description="Commands to install deps and run the finished project",
    )
    challenges: List[Challenge] = Field(
        default_factory=list,
        description="0-2 optional stretch challenges with solutions",
    )


# Back-compat alias used by older main.py imports during transition
Course = ProjectTutorial