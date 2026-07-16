import type { ProjectTutorial, Difficulty, ProjectSize } from "./types/course";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5001";

export interface GenerateParams {
  topic: string;
  difficulty: Difficulty;
  size: ProjectSize;
}

export async function generateTutorialStream(
  params: GenerateParams,
  onStatus: (message: string) => void
): Promise<ProjectTutorial> {
  const res = await fetch(`${BASE}/api/generate/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
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
      const line = chunk
        .split("\n")
        .find((l) => l.startsWith("data: "));
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

export function exportTutorial(id: string) {
  window.open(`${BASE}/api/tutorials/${id}/export`, "_blank");
}

export const generateCourseStream = generateTutorialStream;
export const exportCourse = exportTutorial;