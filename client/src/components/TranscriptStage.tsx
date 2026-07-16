import type { ProjectTutorial, BuildStep } from "../types/course";

type View = "steps" | "overview" | "challenges";

interface Props {
  tutorial: ProjectTutorial;
  step: BuildStep | null;
  stepIndex: number;
  view: View;
}

function wordCount(t?: string) {
  return (t || "").trim().split(/\s+/).filter(Boolean).length;
}

export default function TranscriptStage({
  tutorial,
  step,
  stepIndex,
  view,
}: Props) {
  if (view === "overview") {
    const qr = tutorial.quality_report;
    return (
      <main className="transcript-stage">
        <div className="transcript-stage-inner">
          <p className="stage-kicker">
            {tutorial.difficulty} · {tutorial.size} · ~{tutorial.estimated_hours}
            h
            {qr ? ` · quality ${Math.round(qr.score)}/100` : ""}
          </p>
          <h1 className="stage-title">{tutorial.title}</h1>
          {tutorial.tagline && (
            <p className="stage-tagline">{tutorial.tagline}</p>
          )}

          <section className="stage-section">
            <h2>What we’re building</h2>
            <div className="stage-prose">{tutorial.problem_statement}</div>
          </section>

          <section className="stage-section">
            <h2>When we’re done</h2>
            <div className="stage-prose">{tutorial.end_state}</div>
          </section>

          {tutorial.description && (
            <section className="stage-section">
              <h2>About this tutorial</h2>
              <div className="stage-prose">{tutorial.description}</div>
            </section>
          )}

          {tutorial.intro_transcript && (
            <section className="stage-section">
              <h2>Intro transcript</h2>
              <p className="stage-meta">
                {wordCount(tutorial.intro_transcript)} words · read aloud
              </p>
              <div className="stage-prose stage-prose-emphasis">
                {tutorial.intro_transcript}
              </div>
            </section>
          )}

          {tutorial.how_to_run && (
            <section className="stage-section">
              <h2>How to run</h2>
              <div className="stage-prose">{tutorial.how_to_run}</div>
            </section>
          )}

          {qr && (
            <section className="stage-section">
              <h2>Quality agents</h2>
              <p className="stage-meta">
                Structure · practices · code review
                {qr.repair?.applied ? " · auto-repaired" : ""}
              </p>
              <div className="stage-prose stage-prose-emphasis">
                Score {Math.round(qr.score)}/100
                {qr.passed ? " — passed" : " — review remaining findings"}.{" "}
                {qr.findings_count} finding(s) after repair ({qr.error_count}{" "}
                errors, {qr.warning_count} warnings).
                {qr.repair?.summary ? ` ${qr.repair.summary}` : ""}
              </div>
            </section>
          )}
        </div>
      </main>
    );
  }

  if (view === "challenges") {
    const list = tutorial.challenges || [];
    return (
      <main className="transcript-stage">
        <div className="transcript-stage-inner">
          <p className="stage-kicker">Stretch goals</p>
          <h1 className="stage-title">Challenges</h1>
          {list.length === 0 ? (
            <p className="stage-meta">No challenges for this tutorial.</p>
          ) : (
            list.map((ch, i) => (
              <section key={i} className="stage-section">
                <h2>
                  {i + 1}. {ch.title}
                </h2>
                <div className="stage-prose">{ch.description}</div>
                <h3 className="stage-subhead">Build process</h3>
                <div className="stage-prose">{ch.build_process}</div>
                <h3 className="stage-subhead">Solution walkthrough</h3>
                <div className="stage-prose">{ch.solution_walkthrough}</div>
              </section>
            ))
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="transcript-stage">
      <div className="transcript-stage-inner">
        <p className="stage-kicker">
          Step {step?.step_number ?? stepIndex + 1} of {tutorial.steps.length}
          {step?.is_checkpoint ? " · checkpoint" : ""}
        </p>
        <h1 className="stage-title">{step?.title || "Step"}</h1>
        {step?.goal && <p className="stage-tagline">{step.goal}</p>}

        {stepIndex === 0 && tutorial.intro_transcript && (
          <section className="stage-section">
            <h2>Tutorial intro</h2>
            <p className="stage-meta">
              {wordCount(tutorial.intro_transcript)} words
            </p>
            <div className="stage-prose stage-prose-emphasis">
              {tutorial.intro_transcript}
            </div>
          </section>
        )}

        <section className="stage-section">
          <h2>Transcript</h2>
          <p className="stage-meta">
            {wordCount(step?.speaker_notes)} words · speak while building
          </p>
          <div className="stage-prose stage-prose-emphasis">
            {step?.speaker_notes ||
              "No transcript for this step. Re-generate the tutorial."}
          </div>
        </section>

        {step &&
          stepIndex === tutorial.steps.length - 1 &&
          tutorial.outro_transcript && (
            <section className="stage-section">
              <h2>Outro</h2>
              <p className="stage-meta">
                {wordCount(tutorial.outro_transcript)} words
              </p>
              <div className="stage-prose stage-prose-emphasis">
                {tutorial.outro_transcript}
              </div>
            </section>
          )}
      </div>
    </main>
  );
}