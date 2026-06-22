import type { HarnessMeta, RunRecord } from "../types";

/** Which tools were selected vs left out, plus fast-path / guard signals. */
export function RoutingSummary({ record, meta }: { record: RunRecord; meta: HarnessMeta | null }) {
  const allTools = meta?.tools.map((t) => t.tool_id) ?? [];
  const selected = new Set(record.manifest?.selected ?? []);
  const leftOut = allTools.filter((t) => !selected.has(t));

  return (
    <div className="card">
      <h2>Routing</h2>
      <div className="row">
        {record.fast_path && <span className="badge guard">fast-path</span>}
        <span>
          selected <strong>{selected.size}</strong>/{allTools.length || "?"}
        </span>
        {leftOut.length > 0 && (
          <span className="muted">left out: {leftOut.join(", ")}</span>
        )}
        {record.guards.length > 0 && (
          <span className="badge guard">guard forced: {record.guards.join(", ")}</span>
        )}
        {record.fallback && <span className="badge dropped">fallback: {record.fallback}</span>}
      </div>
    </div>
  );
}
