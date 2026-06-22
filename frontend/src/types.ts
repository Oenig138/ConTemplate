// TypeScript mirrors of the backend Pydantic shapes (contemplate/models.py,
// eval/harness.py, server/meta.py). Kept in sync by hand; the backend is the
// source of truth.

export type Dial = "off" | "medium" | "high";
export type WebMode = "auto" | "on" | "off";
export type Status = "ok" | "empty" | "malformed";
export type Confidence = "high" | "medium" | "low";
export type Trust = "high" | "low";

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  cached_tokens: number;
  cost_usd: number | null;
}

export interface BaselineResult {
  answer: string;
  status: Status;
  usage: Usage;
}

export interface RoutingManifest {
  fast_path: boolean;
  selected: string[];
  rationale: Record<string, string>;
}

export interface DiagnosticResult {
  tool_id: string;
  output: string;
  self_confidence: Confidence;
  status: Status;
  citations: string[];
  usage: Usage;
}

export interface GateDecision {
  tool_id: string;
  admitted: boolean;
  trust: Trust;
  reason: string;
}

export interface RunRecord {
  id: string;
  created_at: string;
  prompt: string;
  dial: string;
  answer: string;
  fast_path: boolean;
  fallback: string | null;
  baseline: BaselineResult | null;
  manifest: RoutingManifest | null;
  guards: string[];
  diagnostics: DiagnosticResult[];
  gate_decisions: GateDecision[];
  total_usage: Usage;
}

export interface RunSummary {
  id: string;
  created_at: string;
  prompt: string;
  dial: string;
  fast_path: boolean;
  fallback: string | null;
  selected: string[];
  cost_usd: number | null;
}

export interface ToolMeta {
  tool_id: string;
  catches: string;
  shielded: boolean;
  retrieval: boolean;
}

export interface HarnessMeta {
  tools: ToolMeta[];
  dials: Record<string, number>;
  models: Record<string, string>;
  knowledge_cutoff: string;
  model_id: string;
}

export interface Budget {
  limit: number | null;
  usage: number;
  remaining: number | null;
  source: string;
}

// Eval shapes
export interface PromptResult {
  prompt_id: string;
  kind: string;
  fast_path: boolean;
  fallback: string | null;
  selected: string[];
  admitted: string[];
  dropped: Record<string, string>;
  divergence: Record<string, number>;
  judge_winner: string | null;
  prompt_text: string;
  baseline_answer: string;
  harness_answer: string;
}

export interface EvalSummary {
  n_prompts: number;
  harness_wins: number;
  single_wins: number;
  ties: number;
  tool_selected: Record<string, number>;
  tool_admitted: Record<string, number>;
  results: PromptResult[];
}

// Stage-event payloads streamed during a run.
export type StageEventType =
  | "run_started"
  | "baseline_done"
  | "orchestrator_done"
  | "selection_done"
  | "fanout_started"
  | "diagnostic_done"
  | "gate_done"
  | "synthesis_started"
  | "run_complete";

export interface StageEvent {
  type: StageEventType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload: Record<string, any>;
}
