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

export type AgentName = "structure" | "practices" | "code" | "repair";
export type FindingSeverity = "info" | "warning" | "error";

export interface QualityFinding {
  agent: AgentName;
  severity: FindingSeverity;
  code: string;
  message: string;
  location?: string;
  suggestion?: string;
}

export interface QualityReview {
  agent: AgentName | string;
  passed: boolean;
  summary: string;
  findings: QualityFinding[];
}

export interface RepairAction {
  action: string;
  location?: string;
  detail?: string;
}

export interface QualityRepair {
  applied: boolean;
  summary: string;
  actions: RepairAction[];
  remaining_issues?: string[];
}

export interface QualityReport {
  passed: boolean;
  score: number;
  reviews: QualityReview[];
  repair?: QualityRepair | null;
  findings_count: number;
  error_count: number;
  warning_count: number;
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
  quality_report?: QualityReport | null;
}

/** @deprecated use ProjectTutorial */
export type Course = ProjectTutorial;