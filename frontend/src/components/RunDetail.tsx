import type { HarnessMeta, RunRecord } from "../types";
import { AnswerPanel } from "./AnswerPanel";
import { DiagnosticCard } from "./DiagnosticCard";
import { RoutingSummary } from "./RoutingSummary";
import { TelemetryStrip } from "./TelemetryStrip";
import { lexicalDivergence } from "./util";

/** The full read-only view of one completed run. Shared by Run and History. */
export function RunDetail({ record, meta }: { record: RunRecord; meta: HarnessMeta | null }) {
  const baseline = record.baseline?.answer ?? "";
  const decisionFor = (id: string) => record.gate_decisions.find((d) => d.tool_id === id);
  const shielded = new Set(meta?.tools.filter((t) => t.shielded).map((t) => t.tool_id) ?? []);

  return (
    <>
      <div className="run-body">
        <AnswerPanel record={record} />
        <div className="card">
          <h2>
            Diagnostics ({record.diagnostics.length} ran ·{" "}
            {record.gate_decisions.filter((d) => d.admitted).length} admitted)
          </h2>
          {record.diagnostics.length === 0 && (
            <p className="muted">No diagnostics ran — the orchestrator took the fast-path.</p>
          )}
          {record.diagnostics.map((diag) => (
            <DiagnosticCard
              key={diag.tool_id}
              diag={diag}
              decision={decisionFor(diag.tool_id)}
              rationale={record.manifest?.rationale[diag.tool_id]}
              shielded={shielded.has(diag.tool_id)}
              divergence={lexicalDivergence(diag.output, baseline)}
            />
          ))}
        </div>
      </div>
      <RoutingSummary record={record} meta={meta} />
      <TelemetryStrip record={record} />
    </>
  );
}
