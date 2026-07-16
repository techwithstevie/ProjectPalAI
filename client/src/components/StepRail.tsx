import type { ProjectTutorial, BuildStep } from "../types/course";

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

export default function StepRail({ tutorial, step, view }: Props) {
    if (view === "overview") {
        return (
            <aside className="step-rail">
                <div className="rail-header">
                    <h3>Key points</h3>
                    <p>Stack, layout, and outcomes for this project.</p>
                </div>
                <div className="rail-scroll">
                    <section className="rail-section">
                        <h4>Stack</h4>
                        <ul className="rail-bullets">
                            {tutorial.stack.map((s, i) => (
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
                            {tutorial.repo_layout.map((p, i) => (
                                <li key={i}>
                                    <code>{p}</code>
                                </li>
                            ))}
                        </ul>
                    </section>

                    <section className="rail-section">
                        <h4>Learning outcomes</h4>
                        <ul className="rail-bullets">
                            {tutorial.learning_outcomes.map((o, i) => (
                                <li key={i}>{o}</li>
                            ))}
                        </ul>
                    </section>

                    <section className="rail-section">
                        <h4>Best practices</h4>
                        <ul className="rail-bullets">
                            {tutorial.best_practices.map((b, i) => (
                                <li key={i}>{b}</li>
                            ))}
                        </ul>
                    </section>

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