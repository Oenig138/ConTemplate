import { useRef, useState } from "react";
import { streamRun } from "../api";
import type { Dial, HarnessMeta, RunRecord, StageEvent, WebMode } from "../types";
import { PipelineTracker, StageState, TrackedTool } from "./PipelineTracker";
import { RunDetail } from "./RunDetail";

const STAGES = [
  { key: "baseline", label: "baseline" },
  { key: "orchestrator", label: "orchestrator" },
  { key: "fanout", label: "fan-out" },
  { key: "gate", label: "gate" },
  { key: "synthesis", label: "synthesis" },
];

interface Live {
  stages: Record<string, StageState>;
  tools: TrackedTool[];
}

const freshLive = (): Live => ({
  stages: Object.fromEntries(STAGES.map((s) => [s.key, "pending"])) as Record<string, StageState>,
  tools: [],
});

export function RunView({ meta, onRunComplete }: { meta: HarnessMeta | null; onRunComplete: () => void }) {
  const [prompt, setPrompt] = useState("");
  const [dial, setDial] = useState<Dial>("high");
  const [web, setWeb] = useState<WebMode>("auto");
  const [running, setRunning] = useState(false);
  const [live, setLive] = useState<Live>(freshLive());
  const [record, setRecord] = useState<RunRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closer = useRef<(() => void) | null>(null);

  const shielded = new Set(meta?.tools.filter((t) => t.shielded).map((t) => t.tool_id) ?? []);

  function handleEvent(ev: StageEvent) {
    setLive((prev) => applyEvent(prev, ev, shielded));
  }

  function start() {
    if (!prompt.trim() || running) return;
    setError(null);
    setRecord(null);
    setLive(freshLive());
    setRunning(true);
    closer.current?.();
    closer.current = streamRun(prompt, dial, web, {
      onEvent: handleEvent,
      onComplete: (rec) => {
        setRecord(rec);
        setRunning(false);
        onRunComplete();
      },
      onError: (msg) => {
        setError(msg);
        setRunning(false);
      },
    });
  }

  const stages = STAGES.map((s) => ({ ...s, state: live.stages[s.key] }));

  return (
    <>
      <div className="card">
        <textarea
          className="prompt-input"
          placeholder="Ask anything — the harness will route diagnostics to refine the answer."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) start();
          }}
        />
        <div className="row" style={{ marginTop: 12 }}>
          <span className="control-label">Dial</span>
          <Segmented<Dial> value={dial} onChange={setDial} options={["off", "medium", "high"]} />
          <span className="control-label" style={{ marginLeft: 12 }}>Web</span>
          <Segmented<WebMode> value={web} onChange={setWeb} options={["auto", "on", "off"]} />
          <button className="run-btn" onClick={start} disabled={running || !prompt.trim()}>
            {running ? "Running…" : "Run ▶"}
          </button>
        </div>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}
      {(running || record) && <PipelineTracker stages={stages} tools={live.tools} />}
      {record && <RunDetail record={record} meta={meta} />}
    </>
  );
}

function applyEvent(prev: Live, ev: StageEvent, shielded: Set<string>): Live {
  const stages = { ...prev.stages };
  let tools = prev.tools;
  switch (ev.type) {
    case "run_started":
      stages.baseline = "active";
      stages.orchestrator = "active";
      break;
    case "baseline_done":
      stages.baseline = "done";
      break;
    case "orchestrator_done":
      stages.orchestrator = "done";
      break;
    case "selection_done":
      tools = (ev.payload.selected as string[]).map((id) => ({
        tool_id: id,
        state: "pending" as const,
        shielded: shielded.has(id),
      }));
      break;
    case "fanout_started":
      stages.fanout = "active";
      tools = tools.map((t) => ({ ...t, state: "running" }));
      break;
    case "diagnostic_done":
      tools = tools.map((t) =>
        t.tool_id === ev.payload.tool_id ? { ...t, state: "done" } : t,
      );
      break;
    case "gate_done":
      stages.fanout = "done";
      stages.gate = "done";
      break;
    case "synthesis_started":
      stages.synthesis = "active";
      break;
    case "run_complete":
      for (const k of Object.keys(stages)) {
        if (stages[k] !== "pending") stages[k] = "done";
      }
      break;
  }
  return { stages, tools };
}

function Segmented<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: T[];
}) {
  return (
    <span className="segmented">
      {options.map((o) => (
        <button key={o} className={value === o ? "active" : ""} onClick={() => onChange(o)}>
          {o}
        </button>
      ))}
    </span>
  );
}
