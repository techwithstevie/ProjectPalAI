import type { ProjectTutorial, Difficulty, ProjectSize } from "./types/course";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5001";

export interface GenerateParams {
  topic: string;
  difficulty: Difficulty;
  size: ProjectSize;
  run_agents?: boolean;
  use_llm_review?: boolean;
  use_llm_repair?: boolean;
}

export async function generateTutorialStream(
  params: GenerateParams,
  onStatus: (message: string) => void
): Promise<ProjectTutorial> {
  const res = await fetch(`${BASE}/api/generate/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic: params.topic,
      difficulty: params.difficulty,
      size: params.size,
      run_agents: params.run_agents ?? true,
      use_llm_review: params.use_llm_review ?? true,
      use_llm_repair: params.use_llm_repair ?? true,
    }),
  });

  if (!res.ok || !res.body) {
    throw new Error(`Generate failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let tutorial: ProjectTutorial | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const payload = JSON.parse(line.slice(6));
      if (payload.type === "status") onStatus(payload.message);
      if (payload.type === "error") throw new Error(payload.message);
      if (payload.type === "complete") {
        tutorial = payload.tutorial as ProjectTutorial;
      }
    }
  }

  if (!tutorial) throw new Error("No tutorial returned");
  return tutorial;
}

export async function generateTutorial(
  params: GenerateParams
): Promise<ProjectTutorial> {
  const res = await fetch(`${BASE}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic: params.topic,
      difficulty: params.difficulty,
      size: params.size,
      run_agents: params.run_agents ?? true,
      use_llm_review: params.use_llm_review ?? true,
      use_llm_repair: params.use_llm_repair ?? true,
    }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Generate failed: ${res.status}`);
  }
  return res.json();
}

export function exportTutorial(id: string) {
  window.open(`${BASE}/api/tutorials/${id}/export`, "_blank");
}

export async function reReviewTutorial(
  id: string,
  opts?: { use_llm_review?: boolean; use_llm_repair?: boolean }
): Promise<ProjectTutorial> {
  const q = new URLSearchParams();
  if (opts?.use_llm_review !== undefined) {
    q.set("use_llm_review", String(opts.use_llm_review));
  }
  if (opts?.use_llm_repair !== undefined) {
    q.set("use_llm_repair", String(opts.use_llm_repair));
  }
  const qs = q.toString();
  const res = await fetch(
    `${BASE}/api/tutorials/${id}/review${qs ? `?${qs}` : ""}`,
    { method: "POST" }
  );
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Review failed: ${res.status}`);
  }
  return res.json();
}

export async function listTutorials(): Promise<
  {
    id: string;
    title: string;
    difficulty: string;
    size: string;
    steps: number;
    quality_score?: number;
    quality_passed?: boolean;
  }[]
> {
  const res = await fetch(`${BASE}/api/tutorials`);
  if (!res.ok) throw new Error(`List failed: ${res.status}`);
  const data = await res.json();
  return data.tutorials || [];
}

export const generateCourseStream = generateTutorialStream;
export const exportCourse = exportTutorial;