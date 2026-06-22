import type { Budget } from "../types";

/** Session budget meter — real OpenRouter balance when available. */
export function BudgetMeter({ budget }: { budget: Budget | null }) {
  if (!budget) return <span className="budget muted">budget —</span>;

  const { limit, usage, remaining } = budget;
  if (limit == null || remaining == null) {
    return (
      <span className="budget" title={`source: ${budget.source}`}>
        spent ${usage.toFixed(2)}
      </span>
    );
  }

  const fraction = Math.max(0, Math.min(1, remaining / limit));
  const level = fraction < 0.1 ? "crit" : fraction < 0.25 ? "low" : "";
  return (
    <span className="budget" title={`source: ${budget.source}`}>
      <span className="bar">
        <span className={`fill ${level}`} style={{ width: `${fraction * 100}%` }} />
      </span>
      ${remaining.toFixed(2)} / ${limit.toFixed(2)}
    </span>
  );
}
