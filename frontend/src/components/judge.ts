// Build a blind A/B judge prompt for pasting into an external model.
//
// The two answers are labelled neutrally (A / B) so the external judge is not
// biased by knowing which came from the harness. The order is flipped
// deterministically per prompt to blunt position bias; the caller keeps the
// key (which letter is the harness) and shows it in the UI, never in the
// copied text.

const INSTRUCTION =
  "You are an impartial judge in a blind comparison. Two AI assistants each " +
  "answered the same prompt. Decide which answer is better — more correct, " +
  "insightful, and genuinely useful — or whether they tie. Give 2–4 sentences " +
  'of reasoning, then end with exactly one line: "Verdict: A", "Verdict: B", ' +
  'or "Verdict: Tie".';

export interface JudgeBlock {
  text: string;
  harnessLetter: "A" | "B";
}

/** Deterministic per-id coin so the same prompt always flips the same way. */
function flipFor(seedKey: string): boolean {
  let h = 0;
  for (let i = 0; i < seedKey.length; i++) h = (h * 31 + seedKey.charCodeAt(i)) | 0;
  return (h & 1) === 1;
}

export function buildJudgeBlock(
  seedKey: string,
  prompt: string,
  harnessAnswer: string,
  singleAnswer: string,
): JudgeBlock {
  const flip = flipFor(seedKey);
  const answerA = flip ? singleAnswer : harnessAnswer;
  const answerB = flip ? harnessAnswer : singleAnswer;
  const text =
    `${INSTRUCTION}\n\n` +
    `=== USER PROMPT ===\n${prompt}\n\n` +
    `=== ANSWER A ===\n${answerA}\n\n` +
    `=== ANSWER B ===\n${answerB}\n`;
  return { text, harnessLetter: flip ? "B" : "A" };
}

/** Concatenate several blocks for batch judging; returns text + per-item key. */
export function buildJudgeBatch(
  items: { seedKey: string; label: string; prompt: string; harnessAnswer: string; singleAnswer: string }[],
): { text: string; keys: { label: string; harnessLetter: "A" | "B" }[] } {
  const blocks: string[] = [];
  const keys: { label: string; harnessLetter: "A" | "B" }[] = [];
  items.forEach((it, i) => {
    const block = buildJudgeBlock(it.seedKey, it.prompt, it.harnessAnswer, it.singleAnswer);
    blocks.push(`########## ITEM ${i + 1}: ${it.label} ##########\n\n${block.text}`);
    keys.push({ label: it.label, harnessLetter: block.harnessLetter });
  });
  return { text: blocks.join("\n\n"), keys };
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
