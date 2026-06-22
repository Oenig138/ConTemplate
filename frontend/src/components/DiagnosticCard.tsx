import { useState } from "react";
import type { DiagnosticResult, GateDecision } from "../types";

interface Props {
  diag: DiagnosticResult;
  decision: GateDecision | undefined;
  rationale: string | undefined;
  shielded: boolean;
  divergence: number;
}

/** One collapsible diagnostic: rationale, gate verdict, output, sources. */
export function DiagnosticCard({ diag, decision, rationale, shielded, divergence }: Props) {
  const [open, setOpen] = useState(false);

  const verdict = !decision
    ? null
    : !decision.admitted
      ? <span className="badge dropped">dropped: {decision.reason}</span>
      : decision.trust === "low"
        ? <span className="badge low">low-trust</span>
        : <span className="badge admitted">admitted</span>;

  return (
    <div className="diag">
      <div className="diag-head" onClick={() => setOpen((o) => !o)}>
        <span className="name">{diag.tool_id}</span>
        {shielded && <span className="badge shielded">shielded</span>}
        <span className="why">{rationale ?? ""}</span>
        {diag.citations.length > 0 && (
          <span className="badge guard">{diag.citations.length} sources</span>
        )}
        <span className="divergence" title="lexical divergence from baseline">
          <span className="track">
            <span className="lvl" style={{ width: `${Math.round(divergence * 100)}%` }} />
          </span>
          {divergence.toFixed(2)}
        </span>
        {verdict}
        <span className="muted">{open ? "▾" : "▸"}</span>
      </div>
      {open && (
        <div className="diag-body">
          <div className="row" style={{ marginTop: 8 }}>
            <span className={`badge conf-${diag.self_confidence}`}>
              self-confidence: {diag.self_confidence}
            </span>
            {diag.status !== "ok" && <span className="badge dropped">{diag.status}</span>}
          </div>
          <div className="output">{diag.output}</div>
          {diag.citations.length > 0 && (
            <div className="sources">
              {diag.citations.map((url) => (
                <a key={url} href={url} target="_blank" rel="noreferrer">
                  {url}
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
