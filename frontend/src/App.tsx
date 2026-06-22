import { useCallback, useEffect, useState } from "react";
import { getBudget, getMeta } from "./api";
import type { Budget, HarnessMeta } from "./types";
import { BudgetMeter } from "./components/BudgetMeter";
import { RunView } from "./components/RunView";
import { HistoryBrowser } from "./components/HistoryBrowser";
import { EvalDashboard } from "./components/EvalDashboard";

type Tab = "run" | "history" | "eval";

export function App() {
  const [meta, setMeta] = useState<HarnessMeta | null>(null);
  const [budget, setBudget] = useState<Budget | null>(null);
  const [tab, setTab] = useState<Tab>("run");

  const refreshBudget = useCallback(() => {
    getBudget().then(setBudget).catch(() => setBudget(null));
  }, []);

  useEffect(() => {
    getMeta().then(setMeta).catch(() => setMeta(null));
    refreshBudget();
  }, [refreshBudget]);

  return (
    <div className="app">
      <header className="topbar">
        <h1>
          Con<span className="accent">Template</span>
        </h1>
        <nav className="tabs">
          {(["run", "history", "eval"] as Tab[]).map((t) => (
            <button
              key={t}
              className={`tab ${tab === t ? "active" : ""}`}
              onClick={() => setTab(t)}
            >
              {t === "run" ? "Run" : t === "history" ? "History" : "Eval"}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        {meta && <span className="muted mono" style={{ fontSize: 12 }}>{meta.model_id}</span>}
        <BudgetMeter budget={budget} />
      </header>

      {tab === "run" && <RunView meta={meta} onRunComplete={refreshBudget} />}
      {tab === "history" && <HistoryBrowser meta={meta} />}
      {tab === "eval" && <EvalDashboard meta={meta} onComplete={refreshBudget} />}
    </div>
  );
}
