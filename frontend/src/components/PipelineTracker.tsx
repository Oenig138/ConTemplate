export type StageState = "pending" | "active" | "done";
export type ToolState = "pending" | "running" | "done";

export interface TrackedTool {
  tool_id: string;
  state: ToolState;
  shielded: boolean;
}

interface Props {
  stages: { key: string; label: string; state: StageState }[];
  tools: TrackedTool[];
}

/** Animated view of the harness DAG as stage events arrive. */
export function PipelineTracker({ stages, tools }: Props) {
  return (
    <div className="card">
      <h2>Pipeline</h2>
      <div className="pipeline">
        {stages.map((s, i) => (
          <span key={s.key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={`stage ${s.state}`}>
              <span className="dot" />
              {s.label}
            </span>
            {i < stages.length - 1 && <span className="arrow">→</span>}
          </span>
        ))}
      </div>
      {tools.length > 0 && (
        <div className="tool-chips">
          {tools.map((t) => (
            <span
              key={t.tool_id}
              className={`chip ${t.state === "running" ? "running" : t.state === "done" ? "done" : ""} ${
                t.shielded ? "shielded" : ""
              }`}
              title={t.shielded ? "shielded from the baseline" : "consumes the baseline"}
            >
              {t.state === "done" ? "✓ " : t.state === "running" ? "⟳ " : ""}
              {t.tool_id}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
