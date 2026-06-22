import { useState } from "react";
import Markdown from "react-markdown";
import type { RunRecord } from "../types";
import { CopyJudgeButton } from "./CopyJudgeButton";

/** The final answer, with a one-click A/B against the bare single call. */
export function AnswerPanel({ record }: { record: RunRecord }) {
  const [compare, setCompare] = useState(false);
  const baseline = record.baseline?.answer ?? "";
  const canCompare = baseline.trim().length > 0 && baseline !== record.answer;

  return (
    <div className="card">
      <h2>Answer{record.fast_path ? " (fast-path — single call)" : ""}</h2>

      {!compare && (
        <div className="answer">
          <Markdown>{record.answer}</Markdown>
        </div>
      )}

      {compare && (
        <div className="ab-grid">
          <div className="ab-col baseline">
            <h3>Baseline (single call)</h3>
            <div className="answer">
              <Markdown>{baseline}</Markdown>
            </div>
          </div>
          <div className="ab-col final">
            <h3>Harness (synthesized)</h3>
            <div className="answer">
              <Markdown>{record.answer}</Markdown>
            </div>
          </div>
        </div>
      )}

      {canCompare && (
        <div className="row ab-toggle" style={{ gap: 8 }}>
          <button className="tab" onClick={() => setCompare((c) => !c)}>
            {compare ? "← Show final only" : "⇄ Compare with single call"}
          </button>
          <CopyJudgeButton
            seedKey={record.id || record.prompt}
            prompt={record.prompt}
            harnessAnswer={record.answer}
            singleAnswer={baseline}
          />
        </div>
      )}
    </div>
  );
}
