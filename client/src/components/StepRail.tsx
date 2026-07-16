import type {
  ProjectTutorial,
  BuildStep,
  QualityFinding,
} from "../types/course";

type View = "steps" | "overview" | "challenges";

interface Props {
  tutorial: ProjectTutorial;
  step: BuildStep | null;
  stepIndex: number;
  view: View;
}

function CodeBlock({ code, label }: { code: string; label?: string }) {
  if (!code?.trim()) return null;
  return (
    <div className="rail-code-wrap">
      {label && <div className="rail-label">{label}</div>}
      <pre className="rail-code">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function severityClass(sev: string) {
  if (sev === "error") return "finding-error";
  if (sev === "warning") return "finding-warn";
  return "finding-info";
}

function FindingsList({ findings }: { findings: QualityFinding[] }) {
  if (!findings?.length) return null;
  const top = findings.slice(0, 12);
  return (
    <ul className="rail-findings">
      {top.map((f, i) => (
        <li key={i} className={severityClass(f.severity)}>
          <span className="finding-sev">{f.severity}</span>
          <span className="finding-msg">
            <strong>{f.code}</strong>
            {f.location ? ` @ ${f.location}` : ""}: {f.message}
            {f.suggestion ? ` → ${f.suggestion}` : ""}
          </span>
        </li>
      ))}
      {findings.length > 12 && (
        <li className="finding-info">+{findings.length - 12} more…</li>
      )}
    </ul>
  );
}

export default function StepRail({ tutorial, step, view }: Props) {
  if (view === "overview") {
    const qr = tutorial.quality_report;
    return (
      <aside className="step-rail">
        <div className="rail-header">
          <h3>Key points</h3>
          <p>Stack, layout, outcomes, and quality agents.</p>
        </div>
        <div className="rail-scroll">
          {qr && (
            <section className="rail-section">
              <h4>Quality agents</h4>
              <div
                className={`quality-card ${
                  qr.passed ? "quality-pass" : "quality-fail"
                }`}
              >
                <div className="quality-score">
                  {Math.round(qr.score)}
                  <span>/100</span>
                </div>
                <div className="quality-meta">
                  {qr.passed ? "Passed" : "Needs attention"}
                  <br />
                  {qr.findings_count} findings · {qr.error_count} errors ·{" "}
                  {qr.warning_count} warnings
                </div>
              </div>
              <ul className="rail-bullets">
                {(qr.reviews || []).map((r, i) => (
                  <li key={i}>
                    <strong>{r.agent}</strong>
                    {r.passed ? " ✓" : " ·"} — {r.summary}
                  </li>
                ))}
                {qr.repair?.summary && (
                  <li>
                    <strong>repair</strong> — {qr.repair.summary}
                  </li>
                )}
              </ul>
              {(qr.repair?.actions?.length ?? 0) > 0 && (
                <>
                  <div className="rail-label" style={{ marginTop: 10 }}>
                    Repair actions
                  </div>
                  <ul className="rail-bullets">
                    {qr.repair!.actions.slice(0, 10).map((a, i) => (
                      <li key={i}>
                        {a.action}
                        {a.location ? ` @ ${a.location}` : ""}
                        {a.detail ? `: ${a.detail}` : ""}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {(qr.reviews || []).some((r) => r.findings?.length) && (
                <>
                  <div className="rail-label" style={{ marginTop: 10 }}>
                    Open findings
                  </div>
                  <FindingsList
                    findings={(qr.reviews || []).flatMap(
                      (r) => r.findings || []
                    )}
                  />
                </>
              )}
            </section>
          )}

          <section className="rail-section">
            <h4>Stack</h4>
            <ul className="rail-bullets">
              {(tutorial.stack || []).map((s, i) => (
                <li key={i}>
                  <strong>
                    {s.name} {s.version}
                  </strong>
                  {s.purpose ? ` — ${s.purpose}` : ""}
                </li>
              ))}
            </ul>
          </section>

          <section className="rail-section">
            <h4>Repo layout</h4>
            <ul className="rail-bullets">
              {(tutorial.repo_layout || []).map((p, i) => (
                <li key={i}>
                  <code>{p}</code>
                </li>
              ))}
            </ul>
          </section>

          <section className="rail-section">
            <h4>Learning outcomes</h4>
            <ul className="rail-bullets">
              {(tutorial.learning_outcomes || []).map((o, i) => (
                <li key={i}>{o}</li>
              ))}
            </ul>
          </section>

          <section className="rail-section">
            <h4>Best practices</h4>
            <ul className="rail-bullets">
              {(tutorial.best_practices || []).map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </section>

          {(tutorial.prerequisites?.length ?? 0) > 0 && (
            <section className="rail-section">
              <h4>Prerequisites</h4>
              <ul className="rail-bullets">
                {tutorial.prerequisites.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </section>
          )}

          {tutorial.final_project_code?.trim() && (
            <section className="rail-section">
              <h4>Final code</h4>
              <CodeBlock code={tutorial.final_project_code} />
            </section>
          )}
        </div>
      </aside>
    );
  }

  if (view === "challenges") {
    const list = tutorial.challenges || [];
    return (
      <aside className="step-rail">
        <div className="rail-header">
          <h3>Solutions</h3>
          <p>Instructor reference for stretch goals.</p>
        </div>
        <div className="rail-scroll">
          {list.map((ch, i) => (
            <section key={i} className="rail-section">
              <h4>{ch.title}</h4>
              <CodeBlock code={ch.solution_code} label="Solution code" />
              {ch.sample_output?.trim() && (
                <CodeBlock code={ch.sample_output} label="Sample output" />
              )}
            </section>
          ))}
        </div>
      </aside>
    );
  }

  return (
    <aside className="step-rail">
      <div className="rail-header">
        <h3>On this step</h3>
        <p>Bullets and code while you follow the transcript.</p>
      </div>
      <div className="rail-scroll">
        {step?.is_checkpoint && (
          <div className="rail-checkpoint">
            Checkpoint — run and verify before continuing
          </div>
        )}

        <section className="rail-section">
          <h4>Key points</h4>
          <ul className="rail-bullets">
            {(step?.bullets || []).map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </section>

        {step?.files_touched && step.files_touched.length > 0 && (
          <section className="rail-section">
            <h4>Files</h4>
            <ul className="rail-bullets">
              {step.files_touched.map((f, i) => (
                <li key={i}>
                  <code>{f}</code>
                </li>
              ))}
            </ul>
          </section>
        )}

        {step?.code && (
          <section className="rail-section">
            <h4>Code · {step.code.file_path}</h4>
            <CodeBlock code={step.code.code} />
            {step.code.explanation && (
              <p className="rail-note">{step.code.explanation}</p>
            )}
            {step.code.best_practice_notes && (
              <p className="rail-note">
                <strong>Best practice:</strong> {step.code.best_practice_notes}
              </p>
            )}
            {step.code.expected_output?.trim() && (
              <CodeBlock
                code={step.code.expected_output}
                label="Expected output"
              />
            )}
          </section>
        )}
      </div>
    </aside>
  );
}