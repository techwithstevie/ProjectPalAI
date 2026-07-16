export type Difficulty = "beginner" | "intermediate" | "advanced";
export type ProjectSize = "small" | "medium" | "monolithic";

export interface StackPackage {
  name: string;
  version: string;
  purpose: string;
}

export interface CodeBlock {
  language: "python";
  file_path: string;
  code: string;
  explanation: string;
  expected_output?: string;
  best_practice_notes?: string;
}

export interface BuildStep {
  step_number: number;
  title: string;
  goal: string;
  bullets: string[];
  speaker_notes: string;
  code?: CodeBlock | null;
  files_touched?: string[];
  is_checkpoint?: boolean;
}

export interface Challenge {
  title: string;
  description: string;
  build_process: string;
  solution_code: string;
  solution_walkthrough: string;
  sample_output?: string;
}

export interface ProjectTutorial {
  id: string;
  title: string;
  tagline: string;
  description: string;
  difficulty: Difficulty;
  size: ProjectSize;
  estimated_hours: number;
  problem_statement: string;
  end_state: string;
  prerequisites: string[];
  learning_outcomes: string[];
  repo_layout: string[];
  stack: StackPackage[];
  best_practices: string[];
  intro_transcript: string;
  steps: BuildStep[];
  outro_transcript: string;
  final_project_code: string;
  how_to_run: string;
  challenges: Challenge[];
}

/** @deprecated use ProjectTutorial */
export type Course = ProjectTutorial;