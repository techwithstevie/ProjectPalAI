import type { ProjectTutorial } from "../types/course";

type View = "steps" | "overview" | "challenges";

interface Props {
    tutorial: ProjectTutorial;
    stepIdx: number;
    view: View;
    onSelectStep: (i: number) => void;
    onSelectOverview: () => void;
    onSelectChallenges: () => void;
}

export default function StepSidebar({
    tutorial,
    stepIdx,
    view,
    onSelectStep,
    onSelectOverview,
    onSelectChallenges,
}: Props) {
    const diff =
        tutorial.difficulty.charAt(0).toUpperCase() + tutorial.difficulty.slice(1);

    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <h2 className="sidebar-course-title">{tutorial.title}</h2>
                <div className="sidebar-meta">
                    <span className="badge badge-gold">{tutorial.size}</span>
                    <span className="badge badge-blue">{diff}</span>
                    <span className="badge">~{tutorial.estimated_hours}h</span>
                </div>
            </div>

            <div className="sidebar-scroll">
                <div className="nav-module">
                    <button
                        type="button"
                        className={`nav-module-btn ${view === "overview" ? "active" : ""}`}
                        onClick={onSelectOverview}
                    >
                        <span className="nav-index">◆</span>
                        <span className="nav-label">Project overview</span>
                    </button>
                </div>

                <div className="nav-module">
                    <div
                        className="nav-module-btn"
                        style={{ cursor: "default", opacity: 0.7 }}
                    >
                        <span className="nav-index">⌘</span>
                        <span className="nav-label">Build steps</span>
                    </div>
                    {tutorial.steps.map((st, i) => (
                        <button
                            key={i}
                            type="button"
                            className={`nav-slide-btn ${view === "steps" && i === stepIdx ? "active" : ""
                                }`}
                            onClick={() => onSelectStep(i)}
                            style={{ paddingLeft: 40 }}
                        >
                            <span className="nav-slide-num">
                                {String(st.step_number).padStart(2, "0")}
                            </span>
                            <span>
                                {st.code ? "⌘ " : ""}
                                {st.is_checkpoint ? "● " : ""}
                                {st.title}
                            </span>
                        </button>
                    ))}
                </div>

                {(tutorial.challenges?.length ?? 0) > 0 && (
                    <div className="nav-module" style={{ marginTop: 12 }}>
                        <button
                            type="button"
                            className={`nav-module-btn ${view === "challenges" ? "active" : ""
                                }`}
                            onClick={onSelectChallenges}
                        >
                            <span className="nav-index">★</span>
                            <span className="nav-label">Challenges</span>
                        </button>
                    </div>
                )}
            </div>
        </aside>
    );
}