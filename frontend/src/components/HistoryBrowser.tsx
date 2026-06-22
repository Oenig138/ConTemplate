import { useEffect, useState } from "react";
import { getRun, getRuns } from "../api";
import type { HarnessMeta, RunRecord, RunSummary } from "../types";
import { RunDetail } from "./RunDetail";
import { fmtCost, fmtTime } from "./util";

/** Browse persisted runs; click one to reopen it read-only. */
export function HistoryBrowser({ meta }: { meta: HarnessMeta | null }) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<RunRecord | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRuns()
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, []);

  if (selected) {
    return (
      <>
        <button className="tab" style={{ marginTop: 16 }} onClick={() => setSelected(null)}>
          ← Back to history
        </button>
        <RunDetail record={selected} meta={meta} />
      </>
    );
  }

  return (
    <div className="card">
      <h2>Run history</h2>
      {loading && <p className="muted">Loading…</p>}
      {!loading && runs.length === 0 && (
        <div className="empty">No runs yet. Head to the Run tab to create one.</div>
      )}
      {runs.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Prompt</th>
              <th>Dial</th>
              <th>Routing</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} className="clickable" onClick={() => getRun(r.id).then(setSelected)}>
                <td className="muted mono">{fmtTime(r.created_at)}</td>
                <td>{r.prompt.length > 80 ? r.prompt.slice(0, 80) + "…" : r.prompt}</td>
                <td className="mono">{r.dial}</td>
                <td className="mono">
                  {r.fast_path ? "fast-path" : r.selected.join(", ") || "—"}
                  {r.fallback ? ` · ${r.fallback}` : ""}
                </td>
                <td className="mono">{fmtCost(r.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
