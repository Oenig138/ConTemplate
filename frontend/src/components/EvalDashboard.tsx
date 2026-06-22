import { useRef, useState } from "react";
import { streamEval } from "../api";
import type { Dial, EvalSummary, HarnessMeta, PromptResult } from "../types";

/** Run the seed-set A/B eval and visualize the per-tool readout (spec §8). */
export function EvalDashboard({ meta, onComplete }: { meta: HarnessMeta | null; onComplete: () => void }) {
  const [dial, setDial] = useState<Dial>("high");
  const [judge, setJudge] = useState(true);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<PromptResult[]>([]);
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closer = useRef<(() => void) | null>(null);

  function start() {
    if (running) return;
    setError(null);
    setResults([]);
    setSummary(null);
    setRunning(true);
    closer.current?.();
    closer.current = streamEval(dial, judge, {
      onPrompt: (r) => setResults((prev) => [...prev, r]),
      onSummary: (s) => {
        setSummary(s);
        setRunning(false);
        onComplete();
      },
      onError: (msg) => {
        setError(msg);
        setRunning(false);
      },
    });
  }

  const tools = meta?.tools.map((t) => t.tool_id) ?? [];
  const meanDivergence = computeMeanDivergence(results, tools);

  return (
    <>
      <div className="card">
        <h2>A/B eval — harness vs single call</h2>
        <p className="muted">
          Runs the held seed set through the harness, comparing each answer against its own
          baseline (the bare single call). Spends API credits — one full run per prompt
          {judge ? ", plus a judge call each" : ""}.
        </p>
        <div className="row">
          <span className="control-label">Dial</span>
          <span className="segmented">
            {(["off", "medium", "high"] as Dial[]).map((d) => (
              <button key={d} className={dial === d ? "active" : ""} onClick={() => setDial(d)}>
                {d}
              </button>
            ))}
          </span>
          <label className="row" style={{ gap: 6, marginLeft: 12 }}>
            <input type="checkbox" checked={judge} onChange={(e) => setJudge(e.target.checked)} />
            <span className="control-label" style={{ margin: 0 }}>blind judge</span>
          </label>
          <button className="run-btn" onClick={start} disabled={running}>
            {running ? `Running… (${results.length})` : "Run eval ▶"}
          </button>
        </div>
        {error && <div className="error-banner">⚠ {error}</div>}
      </div>

      {summary && (
        <div className="card">
          <h2>Aggregate</h2>
          {(summary.harness_wins || summary.single_wins || summary.ties) > 0 ? (
            <div className="stat-grid" style={{ marginBottom: 16 }}>
              <Stat n={summary.harness_wins} l="harness wins" />
              <Stat n={summary.single_wins} l="single wins" />
              <Stat n={summary.ties} l="ties" />
            </div>
          ) : (
            <p className="muted">
              No judge verdicts (set OPENROUTER_JUDGE_MODEL in .env to enable blind judging).
            </p>
          )}
          <table>
            <thead>
              <tr>
                <th>Tool</th>
                <th>Selected</th>
                <th>Admitted</th>
                <th>Mean divergence</th>
              </tr>
            </thead>
            <tbody>
              {tools.map((t) => (
                <tr key={t}>
                  <td>{t}</td>
                  <td className="mono">{summary.tool_selected[t] ?? 0}</td>
                  <td className="mono">{summary.tool_admitted[t] ?? 0}</td>
                  <td className="mono">{meanDivergence[t] != null ? meanDivergence[t].toFixed(2) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {results.length > 0 && (
        <div className="card">
          <h2>Per prompt ({results.length})</h2>
          <table>
            <thead>
              <tr>
                <th>Kind</th>
                <th>Prompt id</th>
                <th>Selected</th>
                <th>Admitted</th>
                <th>Judge</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.prompt_id}>
                  <td>{r.kind}</td>
                  <td className="mono">{r.prompt_id}</td>
                  <td className="mono">{r.fast_path ? "fast-path" : r.selected.join(", ") || "—"}</td>
                  <td className="mono">{r.admitted.join(", ") || "—"}</td>
                  <td>
                    {r.judge_winner ? (
                      <span className={`badge ${r.judge_winner === "harness" ? "admitted" : r.judge_winner === "single" ? "dropped" : "low"}`}>
                        {r.judge_winner}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Stat({ n, l }: { n: number; l: string }) {
  return (
    <div className="stat">
      <div className="n">{n}</div>
      <div className="l">{l}</div>
    </div>
  );
}

function computeMeanDivergence(results: PromptResult[], tools: string[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const tool of tools) {
    const vals = results
      .map((r) => r.divergence[tool])
      .filter((v): v is number => typeof v === "number");
    if (vals.length) out[tool] = vals.reduce((a, b) => a + b, 0) / vals.length;
  }
  return out;
}
