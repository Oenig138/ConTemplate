import { useState } from "react";
import { buildJudgeBlock, copyToClipboard } from "./judge";

interface Props {
  seedKey: string;
  prompt: string;
  harnessAnswer: string;
  singleAnswer: string;
  label?: string;
}

/** Copies a blind A/B judge prompt; reveals which letter is the harness after. */
export function CopyJudgeButton({ seedKey, prompt, harnessAnswer, singleAnswer, label }: Props) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const [letter, setLetter] = useState<"A" | "B" | null>(null);

  const disabled = !harnessAnswer.trim() || !singleAnswer.trim() || harnessAnswer === singleAnswer;

  async function onCopy() {
    const block = buildJudgeBlock(seedKey, prompt, harnessAnswer, singleAnswer);
    const ok = await copyToClipboard(block.text);
    setLetter(block.harnessLetter);
    setState(ok ? "copied" : "failed");
    setTimeout(() => setState("idle"), 4000);
  }

  return (
    <span className="row" style={{ gap: 8 }}>
      <button className="tab" onClick={onCopy} disabled={disabled} title="Copy a blind A/B prompt to judge externally">
        {label ?? "📋 Copy judge prompt"}
      </button>
      {state === "copied" && (
        <span className="badge admitted" title="which letter is the harness answer (don't paste this)">
          copied · {letter} = harness
        </span>
      )}
      {state === "failed" && <span className="badge dropped">clipboard blocked</span>}
      {disabled && <span className="muted" style={{ fontSize: 12 }}>(no distinct baseline to compare)</span>}
    </span>
  );
}
