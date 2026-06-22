import type { RunRecord } from "../types";
import { cachePct, fmtCost, fmtTokens } from "./util";

/** Token / cache / cost telemetry — the live validation of the §9 cost story. */
export function TelemetryStrip({ record }: { record: RunRecord }) {
  const u = record.total_usage;
  return (
    <div className="card">
      <h2>Cost &amp; tokens</h2>
      <div className="telemetry">
        <div className="metric">
          <span className="label">prompt tok</span>
          <span className="value">{fmtTokens(u.prompt_tokens)}</span>
        </div>
        <div className="metric">
          <span className="label">cache hit</span>
          <span className="value">{cachePct(u.prompt_tokens, u.cached_tokens)}</span>
        </div>
        <div className="metric">
          <span className="label">completion tok</span>
          <span className="value">{fmtTokens(u.completion_tokens)}</span>
        </div>
        <div className="metric">
          <span className="label">cost</span>
          <span className="value">{fmtCost(u.cost_usd)}</span>
        </div>
        <div className="metric">
          <span className="label">diagnostics</span>
          <span className="value">{record.diagnostics.length}</span>
        </div>
      </div>
    </div>
  );
}
