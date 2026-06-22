// Typed client for the ConTemplate API. Plain fetch for request/response,
// EventSource for the SSE streams. All paths are relative so the Vite dev
// proxy (and same-origin production) just work.

import type {
  Budget,
  Dial,
  EvalSummary,
  HarnessMeta,
  PromptResult,
  RunRecord,
  RunSummary,
  StageEvent,
  StageEventType,
  WebMode,
} from "./types";

async function getJSON<T>(path: string): Promise<T> {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`${path} → ${resp.status}`);
  return resp.json() as Promise<T>;
}

export const getMeta = () => getJSON<HarnessMeta>("/api/meta");
export const getBudget = () => getJSON<Budget>("/api/budget");
export const getRuns = () => getJSON<RunSummary[]>("/api/runs");
export const getRun = (id: string) => getJSON<RunRecord>(`/api/runs/${id}`);

const STAGE_EVENTS: StageEventType[] = [
  "run_started",
  "baseline_done",
  "orchestrator_done",
  "selection_done",
  "fanout_started",
  "diagnostic_done",
  "gate_done",
  "synthesis_started",
  "run_complete",
];

export interface RunStreamHandlers {
  onEvent: (event: StageEvent) => void;
  onComplete: (record: RunRecord) => void;
  onError: (message: string) => void;
}

/** Open an SSE run stream; returns a closer. */
export function streamRun(
  prompt: string,
  dial: Dial,
  web: WebMode,
  handlers: RunStreamHandlers,
): () => void {
  const qs = new URLSearchParams({ prompt, dial, web });
  const source = new EventSource(`/api/run/stream?${qs}`);

  for (const type of STAGE_EVENTS) {
    source.addEventListener(type, (ev) => {
      const event = JSON.parse((ev as MessageEvent).data) as StageEvent;
      handlers.onEvent(event);
      if (type === "run_complete") {
        source.close();
        if (event.payload.error) handlers.onError(String(event.payload.error));
        else handlers.onComplete(event.payload.record as RunRecord);
      }
    });
  }
  source.onerror = () => {
    source.close();
    handlers.onError("stream connection lost");
  };
  return () => source.close();
}

export interface EvalStreamHandlers {
  onPrompt: (result: PromptResult) => void;
  onSummary: (summary: EvalSummary) => void;
  onError: (message: string) => void;
}

/** Open an SSE eval stream; returns a closer. */
export function streamEval(
  dial: Dial,
  judge: boolean,
  handlers: EvalStreamHandlers,
): () => void {
  const qs = new URLSearchParams({ dial, judge: String(judge) });
  const source = new EventSource(`/api/eval/stream?${qs}`);

  source.addEventListener("prompt_result", (ev) => {
    handlers.onPrompt(JSON.parse((ev as MessageEvent).data) as PromptResult);
  });
  source.addEventListener("eval_summary", (ev) => {
    handlers.onSummary(JSON.parse((ev as MessageEvent).data) as EvalSummary);
    source.close();
  });
  source.onerror = () => {
    source.close();
    handlers.onError("eval stream connection lost");
  };
  return () => source.close();
}
