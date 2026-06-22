# ConTemplate

A diagnostic harness for cheap-model orchestration. It wraps one cheap
near-frontier model (via **OpenRouter**) and refines a baseline answer by
interrogating it from six epistemologically-distinct diagnostic angles, then
integrating the results into a single decisive answer.

See `concept-and-spec.md` for the full concept and the architecture rationale.

## Architecture

```
(baseline ∥ orchestrator + guards) → tool selection → parallel diagnostic
   fan-out → quality gate → synthesis → return
```

| Stage | Module | Responsibility |
|-------|--------|----------------|
| baseline | `contemplate/baseline.py` | the default answer the harness refines |
| orchestrator | `contemplate/orchestrator.py` | routes which diagnostics to run (strict JSON) |
| guards | `contemplate/guards.py` | deterministic empirical-tool routing + overrides |
| diagnostics | `contemplate/diagnostics.py` | the six-tool fan-out (charters in `charters.py`) |
| gate | `contemplate/gate.py` | drops/flags diagnostics; sanity-checks the baseline |
| synthesis | `contemplate/synthesis.py` | directed revision under the diagnostics' constraints |
| pipeline | `contemplate/pipeline.py` | wires the control flow; writes the audit record |

The **six diagnostic tools** — framing, premise, empirical, adversarial,
abductive, genealogical — are each defined by the class of error they catch
(spec §4). Only `empirical` touches the web (OpenRouter web plugin); only
`abductive`/`genealogical` are shielded from the baseline.

## Setup

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env          # add your OPENROUTER_API_KEY
```

**Required before a live run:** edit `config.yaml` and replace the
`REPLACE_ME/...` placeholders with real OpenRouter model slugs — a strong
model for the Pro tier (baseline / orchestrator / synthesis) and a cheaper,
faster one for the Flash tier (diagnostics). Optionally set `provider_pin` to
the provider name so DeepSeek's automatic prefix cache lands on every call.

## Run

```bash
# one prompt through the full harness
./venv/bin/python -m contemplate --dial high "your prompt here"

# force / forbid the web-retrieval tool
./venv/bin/python -m contemplate --no-empirical "an offline/private prompt"

# the A/B eval over the seed prompts (set OPENROUTER_JUDGE_MODEL to enable judging)
./venv/bin/python -m eval.harness
```

Dials are **ceilings, not quotas**: `off`=0, `medium`=3, `high`=5. The
orchestrator may pick fewer, including none (fast-path). Every run writes an
audit JSON to `runs/` with per-call token, cached-token, and cost figures.

## Web interface

A glass-box UI — not a chat box. It surfaces *why* each diagnostic ran, *what*
the gate kept or dropped, and the baseline answer next to the synthesized one,
because "harness beats a single call" is the whole thesis.

```
contemplate/  core harness          server/  FastAPI backend
eval/         A/B eval loop         frontend/  React + TS SPA
```

Three screens: **Run** (live pipeline tracker via SSE, baseline A/B compare,
diagnostic cards with gate verdicts, cost/cache telemetry, session budget
meter), **History** (browse persisted `runs/`), **Eval** (stream the seed-set
A/B with the per-tool selected-vs-admitted readout and blind-judge tally).

Run both halves in dev (two terminals):

```bash
# backend on :8000 (reads .env, fails loud without the key)
./venv/bin/uvicorn server.app:app --port 8000 --reload

# frontend on :5173 (proxies /api to the backend)
cd frontend && npm install && npm run dev
```

Then open <http://localhost:5173>. The backend binds to localhost, sets
security headers, rate-limits the money-spending endpoints, and exposes
`GET /api/health`. The budget meter reads your real OpenRouter balance.

Set `OPENROUTER_JUDGE_MODEL` in `.env` to enable the Eval screen's blind judge.

## Test

```bash
./venv/bin/python -m pytest      # 46 deterministic tests, no API spend
./venv/bin/ruff check contemplate/ server/ tests/ eval/
cd frontend && npm run build     # typecheck + production build
```

The suite mocks the LLM client, so the full pipeline, gate, guards,
orchestrator parsing/repair, event stream, API routes, and eval wiring are all
exercised offline.
