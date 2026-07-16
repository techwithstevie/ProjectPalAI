import { useState } from "react";
import StepSidebar from "./components/StepSidebar.tsx";
import TranscriptStage from "./components/TranscriptStage.tsx";
import StepRail from "./components/StepRail.tsx";
import { generateTutorialStream, exportTutorial } from "./api.ts";
import type {
  ProjectTutorial,
  Difficulty,
  ProjectSize,
} from "./types/course";

type View = "steps" | "overview" | "challenges";

export default function App() {
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>("intermediate");
  const [size, setSize] = useState<ProjectSize>("medium");
  const [tutorial, setTutorial] = useState<ProjectTutorial | null>(null);
  const [stepIdx, setStepIdx] = useState(0);
  const [view, setView] = useState<View>("overview");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");

  const step = tutorial?.steps[stepIdx] ?? null;

  const handleGenerate = async () => {
    if (!topic.trim()) return;
    setLoading(true);
    setStatus("Connecting…");
    try {
      const data = await generateTutorialStream(
        { topic, difficulty, size },
        (m) => setStatus(m)
      );
      setTutorial(data);
      setStepIdx(0);
      setView("overview");
      setStatus("Tutorial ready.");
    } catch (e) {
      alert("Failed: " + (e as Error).message);
      setStatus("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">P</div>
          <div className="brand-text">
            <span className="brand-name">
              Project<span>Pal</span>AI
            </span>
            <span className="brand-tag">Build · Learn · Ship</span>
          </div>
        </div>

        <div className="topbar-divider" />

        <div className="topbar-field">
          <span className="topbar-field-icon">⌕</span>
          <input
            placeholder="What should we build? e.g. CLI todo app with SQLite"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && handleGenerate()}
            disabled={loading}
          />
        </div>

        <select
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value as Difficulty)}
          disabled={loading}
          aria-label="Difficulty"
        >
          <option value="beginner">Beginner</option>
          <option value="intermediate">Intermediate</option>
          <option value="advanced">Advanced</option>
        </select>

        <select
          value={size}
          onChange={(e) => setSize(e.target.value as ProjectSize)}
          disabled={loading}
          aria-label="Project size"
        >
          <option value="small">Small</option>
          <option value="medium">Medium</option>
          <option value="monolithic">Monolithic</option>
        </select>

        <div className="topbar-actions">
          <button
            className="btn btn-primary"
            onClick={handleGenerate}
            disabled={loading || !topic.trim()}
          >
            {loading ? "Building tutorial…" : "Generate with AI"}
          </button>
          {tutorial && (
            <button
              className="btn btn-accent"
              onClick={() => exportTutorial(tutorial.id)}
            >
              Export PPTX
            </button>
          )}
        </div>
      </header>

      {(status || loading) && (
        <div className="status-bar">
          {loading && <span className="pulse" />}
          <span>{status || "Working…"}</span>
        </div>
      )}

      <div className={`main-area ${tutorial ? "" : "main-area-empty"}`}>
        {tutorial ? (
          <>
            <StepSidebar
              tutorial={tutorial}
              stepIdx={stepIdx}
              view={view}
              onSelectStep={(i) => {
                setStepIdx(i);
                setView("steps");
              }}
              onSelectOverview={() => setView("overview")}
              onSelectChallenges={() => setView("challenges")}
            />

            <TranscriptStage
              tutorial={tutorial}
              step={step}
              stepIndex={stepIdx}
              view={view}
            />

            <StepRail
              tutorial={tutorial}
              step={step}
              stepIndex={stepIdx}
              view={view}
            />
          </>
        ) : (
          <div className="empty-state">
            <div className="empty-hero">P</div>
            <h1>Your AI project building pal</h1>
            <p>
              ProjectPalAI turns any idea into a step-by-step build tutorial —
              full spoken transcript in the center, bullets and code on the
              side.
            </p>
            <div className="empty-hints">
              <span>Small · Medium · Monolithic</span>
              <span>Step transcripts</span>
              <span>Modern stack</span>
              <span>Learn by shipping</span>
            </div>
          </div>
        )}
      </div>

      {tutorial && view === "steps" && (
        <footer className="nav-controls">
          <button
            className="btn btn-secondary"
            disabled={stepIdx === 0}
            onClick={() => setStepIdx((i) => Math.max(0, i - 1))}
          >
            ← Previous step
          </button>
          <span>
            Step {stepIdx + 1} of {tutorial.steps.length}
          </span>
          <button
            className="btn btn-secondary"
            disabled={stepIdx >= tutorial.steps.length - 1}
            onClick={() =>
              setStepIdx((i) => Math.min(tutorial.steps.length - 1, i + 1))
            }
          >
            Next step →
          </button>
        </footer>
      )}
    </div>
  );
}