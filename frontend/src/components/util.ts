// Small presentation helpers shared across components.

const WORD = /[a-z0-9]+/g;

/** 1 - Jaccard over word sets; mirrors the eval's divergence proxy. */
export function lexicalDivergence(a: string, b: string): number {
  const wa = new Set(a.toLowerCase().match(WORD) ?? []);
  const wb = new Set(b.toLowerCase().match(WORD) ?? []);
  if (wa.size === 0 && wb.size === 0) return 0;
  let inter = 0;
  for (const w of wa) if (wb.has(w)) inter++;
  const union = wa.size + wb.size - inter;
  return union === 0 ? 0 : 1 - inter / union;
}

export function fmtCost(cost: number | null): string {
  if (cost == null) return "—";
  return `$${cost.toFixed(4)}`;
}

export function fmtTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

export function cachePct(prompt: number, cached: number): string {
  if (prompt === 0) return "0%";
  return `${Math.round((cached / prompt) * 100)}%`;
}

export function fmtTime(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}
