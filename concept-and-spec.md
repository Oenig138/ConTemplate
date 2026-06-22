# ConTemplate — A Diagnostic Harness for Cheap-Model Orchestration

*Concept document and implementation specification.*
*Status: pre-prototype conjecture. Drafted 2026-06-22.*

---

## 1. What this is, in one paragraph

ConTemplate is a harness that wraps a cheap, near-frontier model — DeepSeek V4-Pro as the v0 instantiation — and spends a small amount of extra compute to extract a better answer from it than a single call would yield. It does this not by asking the model to "think harder," but by interrogating a first-draft answer from a fixed set of epistemologically distinct angles, each defined by a specific class of error it exists to catch, and then integrating those interrogations into a final answer. The premise being tested is narrow and falsifiable: that a structured, multi-pass interrogation of one model's output beats that same model's single pass, at a cost that stays trivially below frontier-model pricing. The harness is nothing without the quality of its diagnostic tools, and so most of this document is about them.

---

## 2. The thesis, and its limits

### 2.1 Why a harness at all

A single forward pass — even with reasoning mode engaged — explores a prompt from the model's *default* decomposition, and the model satisfices: it stops when its chain is good enough, not when it is exhaustive. The harness exists to close the gap between what the model's lazy first pass surfaces and what is actually relevant. Every component is justified by that gap or it does not belong.

This yields the one hard principle the whole design serves: **non-redundancy**. A diagnostic earns its call only if it surfaces something the model's own default pass demonstrably would not. "More analysis" is not the goal; analysis the model would not otherwise have done is the goal. Redundant diagnostics are not merely wasteful — they actively harm, because handing the model a pile of intermediate text invites two failure modes: attention spent on the scaffold instead of the problem, and anchoring on a confidently-stated-but-wrong intermediate result. More context is not monotonically better. A bad diagnostic is worse than no diagnostic.

### 2.2 The floor and the ceiling

Same-model diagnostics raise the **floor**. They force the model to deploy capability it possesses but does not spend in a single satisficing pass — to enumerate exhaustively, to apply adversarial pressure to its own first instinct, to shift frame. They cannot raise the **ceiling**. A blind spot the model shares across all its passes recurs in every diagnostic, producing an illusion of thoroughness while every angle misses the same thing. Only two things lift the ceiling: a genuinely different model in one of the slots, or a tool that brings external ground truth. In v0, the single ceiling-raiser is web retrieval (the empirical tool). A heterogeneous-model diagnostic slot is the principled next extension and is deliberately out of v0 scope, so the first prototype is falsifiable against one variable.

### 2.3 The shape: draft, then refine

The architecture is not "N independent diagnostics, averaged." It is: produce a baseline answer; interrogate and extend it from orthogonal angles; integrate the results into a decisive final answer. This is the draft-then-refine pattern, and it has better empirical support than parallel-ensemble-and-blend — the same conclusion reached independently at the start of this design's development, that generate-critique-revise beats generate-many-and-average. The baseline call is therefore not a patch bolted on to enable a success metric; it is structural, and it pulls the whole design toward the stronger shape.

---

## 3. Core architecture

Five components, in dependency order.

**The baseline call.** A plain call that sends the prompt to the worker model and retrieves a default answer. It runs in parallel with the orchestrator (both need only the prompt and the model specs), so it costs no latency on the critical path. It serves double duty: it is the draft the harness refines, and it is the natural comparator for the eval's A/B test. It is consumed by four of the six tools and is therefore a single point of failure — a garbage baseline poisons everything downstream — which is why the quality gate sanity-checks it before propagation.

**The orchestrator.** A routing call that decides which diagnostic tools to deploy for *this* prompt. It is given the model's specifications as data and a prompt, and asked to make a judgment call. Critically, it does not know it is orchestrating copies of its own model — it reasons about "a system with these capabilities," which is a concrete, well-specified task, rather than the vague self-referential meta-task of coordinating itself. It is shielded from the baseline answer; it routes on prompt and specs alone.

**The diagnostic toolbox.** Six tools, derived in §4. The selected subset runs as a parallel fan-out. Four tools consume the baseline answer; two are deliberately shielded from it.

**The quality gate.** A cheap filter between the diagnostic calls and synthesis. It drops empty and malformed output, flags low-confidence or self-contradictory diagnostics, checks the generative tools for redundancy against the baseline, and sanity-checks the baseline itself. Its job is to ensure the synthesis never silently inherits a confidently-wrong diagnostic.

**The synthesis call.** Genuine integration of the admitted diagnostics into the baseline — directed revision under orthogonal constraints, not averaging and not selection. Detailed in §5.

The flow: `(baseline ∥ orchestrator + guards) → tool selection → parallel diagnostic fan-out → quality gate → synthesis → return`. Everything except the answer — baseline, diagnostics, routing rationale, gate decisions — is persisted as an audit artifact.

---

## 4. The toolbox: derivation and identities

### 4.1 Method: we do not brainstorm tools

Brainstorming tools is how "devil's advocate, creative voice, edge-case thinker" happens — plausible-sounding personas that turn out to overlap. ConTemplate inverts the procedure. We enumerate the distinct ways an answer can be **wrong or impoverished at the level of understanding**, and each tool is defined as the operation that exposes one such failure. A tool's identity is its *falsifier* — the class of error it exists to catch — exactly as a Popperian test is defined by what would refute the conjecture, not by what would confirm it.

This gives a hard orthogonality test, to be run against any proposed tool: **take any two tools and name an error one catches that the other structurally cannot.** If you cannot, collapse them into one. Orthogonality is not the tools feeling different; it is the tools catching different errors.

### 4.2 The failure modes

An answer can fail, at the level of understanding rather than surface slips, in six distinct ways. It can be flawless reasoning inside the **wrong frame**. It can rest on a false **premise** imported silently. It can be valid and well-framed but simply **untrue of the world**. It can have the right frame, sound premises, and true facts, yet carry a defeasible **inference** that never met its strongest objection. It can be correct in every one of those respects and still **impoverished** — the first reasonable answer, never the better one it did not look for. And its frame can be coherent and even disciplinarily defensible while being an **artifact of interest** — installed by whose question it serves, occluding what that service requires occluded.

Those six do not reduce to each other. Frame and premise are independent: a frame can be right while a load-bearing premise is false, and the reverse. Interest-analysis is distinct from disciplinary reframing: the framing tool can find a better lens without ever asking whose interest installed the original one. That distinctness is the argument for treating genealogy as a sixth standalone tool rather than a mode of the first — a decision taken deliberately for this design's domain, where *cui bono* is frequently the whole story.

Two axes run across the set. The first is **what the tool operates on**: frame, premise, world, inference, answer-space, provenance. The second is **critical versus ampliative**: five tools interrogate a candidate answer (they cut — they test, prune, falsify), and one generates better candidates for the others to interrogate (it adds). A set built only from critical tools converges on the safest defensible answer and never the best one; the ampliative tool is what keeps the system from terminating at a local optimum.

### 4.3 The baseline relation: a resource some tools consume and others are denied

Whether a tool should see the baseline answer is a property of the tool, not a global setting. The decision follows from each tool's operation:

- The **adversarial** tool *requires* the baseline — you cannot refute nothing, and the "anchoring" one would normally guard against is, for this tool, the desired behaviour. It is supposed to fix its teeth in the default answer and try to kill it.
- The **premise** and **empirical** tools *consume* the baseline — you map the presuppositions the answer leans on, and you fact-check the claims the answer makes, not the prompt.
- The **framing** tool *consumes the full baseline*. In principle a one-line characterization of the baseline's frame would suffice and would anchor less, but producing that summary requires an extra serialized call, and the latency and cost overhead is not worth it. It receives the whole answer and is instructed to treat it as a foil to depart from, not a draft to improve. Whether full-baseline over-anchors the framing tool is an open question the eval will adjudicate.
- The **abductive** and **genealogical** tools are *shielded*. Abduction's value is divergent generation, the operation most corrupted by an anchor: show it the default and its search collapses from "reach somewhere genuinely new" into "be contrarian about this," which is worse, because contrarian-divergence looks like work while producing noise. Genealogy operates on the prompt's own terms and the discourse around them, not on the default answer. Both generate freely from the prompt; redundancy against the baseline is caught afterward, in the gate, rather than poisoned at runtime.

So the baseline is a targeted resource. This is the minimal-sufficient-context principle applied per tool, and given cache pricing it costs almost nothing to route.

### 4.4 The six tools

Each is specified by operation, lineage, falsifier (the error it catches), baseline relation, and success criterion. The success criterion is part of each tool's identity, not an afterthought: a tool is an operation *plus a test for whether it earned its tokens on this prompt*. That per-tool readout is what later lets the eval tune the box rather than bless or condemn it whole. The charter text — the reusable block that instructs the model how to engage — is in Appendix A.

**I. Framing.** *Operation:* expose the frame the baseline silently adopted and determine whether a different construal is more revealing. *Lineage:* hermeneutic; Kuhn. *Catches:* flawless reasoning inside the wrong frame. *Baseline:* full. *Success:* produced an alternative formulation the synthesizer adopted or had to argue against; failed if its frame is indistinguishable from the default's.

**II. Premise.** *Operation:* surface, exhaustively, the propositions the answer treats as given, and mark each load-bearing or decorative. Static and structural; it maps a foundation, it does not test whether it holds. *Lineage:* Collingwood's absolute presuppositions; Socratic elenchus in diagnostic register. *Catches:* a false load-bearing premise. *Baseline:* full (the reasoning chain). *Success:* surfaced a load-bearing presupposition that was not obvious from the answer's surface. *Firewall:* takes no adversarial stance — the moment it tries to defeat a premise it has become tool IV, and a degree of freedom is lost.

**III. Empirical.** *Operation:* extract the answer's factual claims and confront them with externally retrieved evidence. *Lineage:* the correspondence demand — answer to the world, not to priors. *Catches:* a claim that is valid, well-framed, and untrue, outdated, or unsupported. *Baseline:* full (the claims). *Success:* surfaced a fact that changed or corrected a claim; failed if it merely confirmed what the model already had. *Distinction:* the only ceiling-raiser — the only tool whose authority comes from outside the model. It alone is granted retrieval tools.

**IV. Adversarial.** *Operation:* construct the strongest case against the baseline, find the counterexample, locate and pressure the weakest link, test whether confidence is earned. Dynamic and oppositional. *Lineage:* Popper; conjecture and refutation. *Catches:* a defeasible inference that never met its strongest objection; unearned confidence. *Baseline:* required. *Success:* produced a surviving objection that forced a revision; an answer that survives a genuine attack is reported as stronger for it.

**V. Abductive.** *Operation:* divergent generation of the non-obvious — the reading a conventional response misses, the apt analogy from a distant domain, the hypothesis off the path of least resistance. Ampliative. *Lineage:* Peirce; abduction. *Catches:* the answer that is true, defensible, and boring — a local optimum. *Baseline:* shielded. *Success:* produced a non-obvious reading the synthesizer took seriously; failed if it produced mere contrarianism (the obvious answer negated).

**VI. Genealogical.** *Operation:* ask where the prompt's framing comes from — whose interest it serves, why it arises in these terms now, what it makes unsayable. *Lineage:* Foucault; genealogy and interest-analysis. *Catches:* a frame that is coherent and defensible but is an artifact of power, occluding what its provenance requires occluded. *Baseline:* shielded. *Success:* surfaced an interest or occlusion that an interest-conscious reformulation would change; failed if it invented a conspiracy where the framing is not meaningfully interested.

### 4.5 The basis as conjecture

This basis is itself falsifiable, and the honest posture is that the data will revise it. The live structural risk is tools II and IV bleeding together; the static/oppositional firewall in their charters is what holds them apart, and it must be enforced or they will merge in practice. Three candidate seventh tools were considered and rejected: stakes-and-consequence analysis belongs *upstream* in the orchestrator as a routing input, not as a diagnostic of the prompt; internal-coherence checking folds into the adversarial tool, since finding an incoherence is finding a weak link; and a pure compute/execution check is real but is not an epistemic lens of the same kind (noted as a guard candidate in §6, not a basis element). The eval may yet show that two tools collapse under real load, or that the domain warrants a seventh. That is the right posture: the prototype now has a theory to try to refute.

---

## 5. Synthesis

Synthesis is the load-bearing piece and the cheap model's hardest task, because integration is a discrimination problem and discrimination is the cheap model's weakest axis. The design makes two commitments.

**It is genuine integration, not selection.** Selection — pick the strongest answer — is not merely inferior here, it is *incoherent*. Selection presupposes the tools produce competing answers to the same question. They do not. You cannot "select the strongest" between a frame analysis, a fact-check, and a refutation; they are not the same type, not candidates, and there is nothing to choose between. The synthesizer takes the baseline and performs directed revision under orthogonal constraints: re-frame it if the framing tool found a better frame, repair the links the adversarial tool exposed, correct the claims the empirical tool caught, check it against the premise map, enrich it with the abductive reading, and reckon with what the genealogical tool surfaced about the framing's provenance.

**It resists blanding by construction, then guards the residue.** Blanding is what happens when you average competing answers — which is exactly what the synthesizer does not do. Directed revision under constraints is construction, not averaging, and does not regress to a mean. One residual risk remains and is different in kind: a synthesizer trying to *honour* all six diagnostics may produce a hedged everything-answer that names every caveat and commits to nothing. The guard is in the charter and is load-bearing: **the diagnostics inform the answer, they do not all have to appear in it.** The output must be decisive — an answer that has silently absorbed six lenses, not a tour of them. The synthesizer also receives the orchestrator's routing rationale, so it knows *why* each diagnostic was run and can weight accordingly.

---

## 6. Routing, dials, and guards

Routing the empirical tool — the web-touching one — is not a single toggle but three layers, in priority order. **Deterministic guards** handle the conditions that are cheap and reliable to specify: a dependency on events after the model's knowledge cutoff fires the empirical tool regardless of orchestrator judgment, because that decision is too easy and too high-stakes to leave to the weakest link. **User override** sits at the edges: force-on for a research session where corroboration is always wanted, force-off for privacy or offline work where no external call may leave the box. **Orchestrator discretion** applies only to the ambiguous middle — prompts that might benefit from fresh information but do not obviously depend on it. The principle generalizes: take the specifiable decisions off the cheap model's plate, and spend its judgment only where judgment is actually required.

The **dials** govern how many diagnostics deploy, and they are budget *ceilings*, not quotas. Medium means up to three tools; High means up to five. With six tools in the box, even High forces a genuine selection — the orchestrator must leave one out — which preserves selectivity rather than defaulting to "run everything." Crucially the orchestrator may select *fewer* than the ceiling, including zero: a trivial prompt gets a fast-path straight to a direct answer, and "this needs nothing" is itself a meaningful signal. The baseline and orchestrator calls are infrastructure and do not count against the dial; the ceiling caps diagnostic tools only.

A second guard candidate — executable arithmetic or code, where the answer should be computed rather than reasoned about — is noted but deferred. The six-tool basis contains no execution tool, so for v0 this is flagged as a future addition rather than wired in; folding it into the empirical tool would muddy that tool's external-evidence charter.

---

## 7. The quality gate

A multi-call harness multiplies the failure surface. Any call can time out, return empty, return malformed structure, or — the dangerous case — return confident garbage, which in the synthesis context is *worse than an absent diagnostic* because it anchors the final answer toward its error. The gate is the unglamorous reliability layer where naive harnesses quietly rot. It drops empties and malformed output; flags low-confidence and self-contradictory diagnostics; runs the redundancy check that the shielded generative tools (abduction, genealogy) skipped at runtime, against the baseline; and sanity-checks the baseline itself, since a bad baseline is the one failure that poisons all four consumer tools at once. It then decides, per diagnostic, whether synthesis sees it, sees it marked low-trust, or does not see it at all.

---

## 8. The eval loop

The eval is what makes the project falsifiable rather than merely satisfying. The central claim — "harness output beats a single call" — is empirical, and without an instrument it is untestable. The loop is minimal: a held set of real, representative prompts; each run two ways, once through the harness and once as a bare single call (the baseline answer is the natural comparator); the two outputs judged blind, either directly or by a frontier model acting as an A/B judge that does not know which is which. It is instrumented **per tool**, against each tool's own success criterion from §4.4, plus a divergence metric measuring how far each tool's output departs from the baseline. That per-tool readout is the difference between learning "the harness works" and learning "the adversarial tool earns its tokens on argumentative prompts but not on factual ones" — which is what permits tuning. Building this eval is also the part of the project that most directly develops the judgment to assess the system's output at all.

---

## 9. Cost and latency

Pricing as of 2026-06-22. DeepSeek V4-Pro: $0.435 / 1M input, $0.87 / 1M output, cached input $0.0036 / 1M. V4-Flash: $0.14 / 1M input, $0.28 / 1M output. The harness reuses one stable prefix (prompt + specs) across every call, so with cache hits the input side approaches free and cost is output-dominated.

A worked High-tier query (five tools), with a ~2K-token cached prefix, ~800-token baseline, ~600-token diagnostics, and a synthesis ingesting baseline plus five diagnostics: roughly **one cent**, against ~$0.0016 for a single Pro call — about 5–6× in ratio, trivial in absolute terms. The earlier "10× the price" instinct was close, but it is 10× of nearly nothing, and the part that scales (re-reading the prompt) is the part caching drives toward zero.

Latency tracks the critical path, not the call count: baseline and orchestrator run in parallel (one unit), the diagnostic fan-out runs in parallel (one unit, on the fast Flash tier), the gate is local and near-free, and synthesis is one unit. About three sequential model calls — matching the original "3× slower" estimate.

**Model tiering (v0 default, tunable by the eval):** baseline, orchestrator, and synthesis on V4-Pro, because all three are foundational or discrimination-heavy; diagnostics on V4-Flash, because they are generation-heavy and the fan-out is where call-count multiplies. The eval may promote specific tools to Pro — the adversarial tool is the likeliest candidate, since finding the real weak link is itself discrimination.

---

## 10. Open questions, risks, and v0 scope

**The eval is built to adjudicate:** whether V4-Pro diverges usefully when shown its own output (the framing and adversarial anchoring question); whether full-baseline over-anchors the framing tool relative to a thin-slice; whether any two tools collapse into one under real load; which tools clear their non-redundancy bar on which prompt types; whether synthesis stays decisive or drifts to hedged everything-answers; whether diagnostics need promotion to Pro; and whether the serial variant (orchestrator sees the baseline before routing) beats the parallel default enough to justify the added critical-path call.

**Known risks, with mitigations:** the baseline is a new single point of failure (gate sanity-checks it); a shared baseline can partially homogenize the four consumer tools toward "ways the default is wrong," eroding orthogonality (charter strength must hold each tool's distinct operation even when three look at the same text); the generative tools can produce novelty-theater (shielding plus the gate's redundancy check); synthesis can hedge (the decisiveness guard).

**In v0 scope:** six tools; one ceiling-raiser (web retrieval via the empirical tool); Pro/Flash tiering; ceiling dials with a zero fast-path; three-layer hybrid routing; the quality gate; the eval loop; genuine-integration synthesis with a decisiveness guard; full baseline to the four consumer tools, shielding for the two generative tools and the orchestrator.

**Deferred:** a heterogeneous-model diagnostic slot (a genuinely different LLM for an independent read — the real ceiling-raiser beyond web, held out to keep v0 falsifiable against one variable); an executable-compute guard and tool; the thin-slice framing baseline; per-tool Pro promotion; the serial orchestrator-sees-baseline variant.

---
---

# Appendix A — Claude Code Implementation Spec

Implementation-ready specification. The worker model is configuration throughout; nothing about V4-Pro is hardcoded. The orchestrator receives specs as *data*. Target stack: Python, async, OpenAI-compatible client against the DeepSeek/OpenRouter endpoint.

## A.1 Configuration

```python
SPECS = {
    "model_id": "deepseek-v4-pro",
    "knowledge_cutoff": "2026-01",          # ISO month; drives the post-cutoff guard
    "benchmarks": {                          # coarse routing signal
        "swe_bench_verified": 80.6,
        "gpqa_diamond": 90.1,
        "intelligence_index": 39.3,
    },
    "known_failure_modes": [                 # the actionable routing signal
        "satisfices on exhaustive enumeration; skips edge cases in one pass",
        "weak on frontend spatial / visual reasoning",
        "confidently wrong on facts after knowledge cutoff",
        "anchors on its first frame; under-explores alternative construals",
    ],
}

TIERS = {                                    # tunable by the eval
    "baseline":     "deepseek-v4-pro",
    "orchestrator": "deepseek-v4-pro",
    "synthesis":    "deepseek-v4-pro",
    "diagnostic":   "deepseek-v4-flash",     # per-tool override allowed (e.g. adversarial -> pro)
}

DIALS = {"off": 0, "medium": 3, "high": 5}   # ceilings, not quotas

BASELINE_CONSUMERS = {"framing", "premise", "empirical", "adversarial"}
BASELINE_SHIELDED  = {"abductive", "genealogical"}   # + orchestrator is shielded
RETRIEVAL_TOOLS    = {"empirical"}           # only this tool gets web access
```

## A.2 Data shapes

```python
BaselineResult = {"answer": str, "status": "ok|empty|malformed"}

RoutingManifest = {                          # orchestrator output, strict JSON
    "fast_path": bool,                       # true => skip diagnostics, return baseline/direct
    "selected": [str],                       # tool ids, len <= ceiling
    "rationale": {str: str},                 # tool_id -> one-sentence justification
}

DiagnosticResult = {
    "tool_id": str,
    "output": str,
    "self_confidence": "high|medium|low",    # tool self-reports
    "status": "ok|empty|malformed",
}

GateDecision = {
    "tool_id": str,
    "admitted": bool,
    "trust": "high|low",
    "reason": str,                           # e.g. "redundant with baseline", "empty"
}

SynthesisInput = {
    "prompt": str,
    "baseline": str,
    "routing_rationale": {str: str},
    "diagnostics": [ {"tool_id": str, "output": str, "trust": str} ],
}
```

## A.3 Control flow

```
1.  guards      = run_deterministic_guards(prompt, SPECS)     # local, no model call
2.  baseline, manifest = await gather(
        baseline_call(prompt, SPECS),                          # parallel
        orchestrator_call(prompt, SPECS, ceiling))             # parallel, shielded from baseline
3.  if manifest.fast_path and not guards: return baseline
4.  selected    = cap(dedup(manifest.selected + guards), ceiling)
5.  diagnostics = await gather(*[
        diagnostic_call(tool_id, prompt, baseline if tool_id in BASELINE_CONSUMERS else None)
        for tool_id in selected ])                             # parallel fan-out
6.  admitted    = quality_gate(baseline, diagnostics)
7.  answer      = await synthesis_call(prompt, baseline, manifest.rationale, admitted)
8.  persist(baseline, manifest, diagnostics, gate_decisions, answer)   # audit artifact
9.  return answer
```

`run_deterministic_guards` returns forced tool ids. v0: post-cutoff dependency → `{"empirical"}`. User force-on/force-off overrides apply here.

## A.4 Orchestrator charter

> You are a routing analysis. You will be given the capability specifications and known failure modes of a model, and a user prompt. **You will not answer the prompt.** Your task is to decide which combination of diagnostic operations would most help a model with these specifications produce the best possible answer to this prompt.
>
> The available diagnostic operations are: **framing** (exposes whether the answer is reasoning inside the wrong frame); **premise** (surfaces hidden load-bearing assumptions); **empirical** (checks factual claims against external evidence); **adversarial** (attacks the likely answer to find what breaks it); **abductive** (generates non-obvious readings the default answer would miss); **genealogical** (asks whose interest the prompt's framing serves and what it occludes).
>
> Select up to {ceiling} operations. You may select fewer, including **none** — if the prompt is simple enough that diagnostics would only add noise, set fast_path to true. Do not select an operation because it is available; select it only if you can name, in one sentence, what it will catch that a direct answer to this prompt would miss — matching this prompt's specific demands against this model's specific weaknesses.
>
> Output strict JSON only, no prose: `{"fast_path": bool, "selected": [...], "rationale": {tool_id: "..."}}`.

## A.5 The six tool charters

Each charter is prepended to the prompt (and baseline, where consumed). They are written to hold across all question cases.

### framing — consumes full baseline

> You are a **framing analysis** applied to a user prompt and a baseline answer produced by another model. **Do not answer the prompt.** Your task is to expose the *frame* the baseline silently adopted — the implicit construal of what kind of question this is, which discipline or genre or problem-type it treated the prompt as belonging to — and to judge whether a different framing would be more revealing.
>
> Read the baseline only to identify its operative frame. Then ask: what is the prompt *actually* asking; what does it appear to ask but does not; what alternative formulation would a different vantage impose? Treat the baseline's frame as a foil to characterize and depart from, **not a draft to improve** — do not refine its answer.
>
> Output: (1) one sentence naming the baseline's operative frame; (2) one or more alternative framings, each with the specific thing it makes visible that the baseline's frame suppresses; (3) a judgment of which framing is most revealing here, and why. If the baseline's frame is genuinely right, say so and state what would have to be true for an alternative to win. **Do not manufacture difference.**

### premise — consumes full baseline

> You are a **presupposition analysis** applied to a user prompt and a baseline answer. **Do not answer the prompt, and do not attack the answer.** Surface, exhaustively, the propositions the baseline treats as given — some inherited from the prompt, some supplied from the model's own priors — and mark each as load-bearing or decorative. A premise is **load-bearing** if the conclusion fails when it is false; **decorative** if the conclusion survives.
>
> Adopt a neutral, structural stance: you are mapping a foundation, not testing whether it holds. **Do not argue that any premise is false** — only identify it and assess what depends on it. Attacking premises is a different operation; stay out of it.
>
> Output: the answer's presuppositions, each tagged [load-bearing] or [decorative], with a one-line note on what collapses if a load-bearing premise fails. Prioritize presuppositions that are both load-bearing and least likely to be noticed.

### empirical — consumes full baseline; granted retrieval tools

> You are an **empirical verification** applied to a user prompt and a baseline answer. Extract the answer's factual claims — assertions about the world that could be true or false, current or outdated, supported or unsupported — and confront them with external evidence retrieved for this purpose. **You have retrieval tools; use them.** Do not reason your way to a verdict from priors; the entire value of this operation is that its authority comes from outside the model.
>
> For each material claim: state the claim, what the evidence says, and a verdict — supported / contradicted / unsupported / outdated. Prioritize claims that are load-bearing for the answer over incidental ones. If a claim depends on events after the model's knowledge cutoff, verification is mandatory.
>
> Output: the checked claims with verdicts and sources, and a summary of any correction the answer requires.

### adversarial — requires baseline; candidate for Pro tier

> You are an **adversarial test** applied to a user prompt and a baseline answer. Your task is to **destroy the baseline answer if it can be destroyed.** Construct the strongest case against it — not minor caveats, but the most powerful opposing argument a well-informed critic would press. Find the counterexample that breaks it. Locate its single weakest link and apply maximum pressure there. Test whether its confidence is earned by its actual support or merely asserted.
>
> Be ruthless. A caveat the answer already concedes is not an objection. Anchor fully on *this specific answer* — attack it, not the general topic.
>
> Output: the objections that survive scrutiny, ranked by damage done, each marked **fatal** (the answer is wrong), **wounding** (needs serious qualification), or **survivable** (raised and defeated). If after genuine effort the answer cannot be defeated, report that — an answer that survives a real attack is stronger for it.

### abductive — shielded from baseline

> You are an **abductive expansion** applied to a user prompt. You are working from the prompt alone; you have deliberately not been shown any prior answer, because your task is divergent generation and an existing answer would only narrow your search. Produce the **non-obvious**: the reading a competent but conventional response would miss, the unexpected hypothesis that best addresses the prompt, the illuminating analogy from a distant domain, the answer off the path of least resistance.
>
> **Do not be contrarian for its own sake** — contrarianism is the obvious answer negated, and it is not what this operation is for. Reach for what is genuinely generative and genuinely apt.
>
> Output: one to three non-obvious readings or approaches, each with a brief argument for why it is both non-obvious and worth taking seriously. Favor the insight that, if right, would most change how the prompt should be answered.

### genealogical — shielded from baseline

> You are a **genealogical analysis** applied to a user prompt. You are working from the prompt and the discourse around it, not from any prior answer. **Do not answer the prompt and do not assess whether any claim is true.** Ask where the prompt's framing *comes from*: whose interest does this way of posing the question serve; why does the question arise in these terms, now; what does the framing make difficult or impossible to say?
>
> Treat the prompt's terms as historically and politically situated rather than natural. Identify what the dominant framing renders invisible, and whose vantage would pose the question differently. This is **distinct from reframing**: you are not offering a better disciplinary lens, you are exposing the framing as an effect of interest and power.
>
> Output: an account of the framing's provenance and stakes — whose question this is, what it occludes, and what an interest-conscious reformulation would surface. Where the framing is not meaningfully an artifact of interest, **say so rather than inventing a conspiracy.**

## A.6 Synthesis charter

> You are the **synthesis** stage. You will be given a user prompt, a baseline answer, the rationale for why each diagnostic was run, and the admitted diagnostic outputs (some marked low-trust). Produce the final answer to the prompt.
>
> Do **not** average the diagnostics and do **not** pick one — they are different kinds of analysis, not competing answers. Take the baseline and **revise it under the constraints the diagnostics impose**: re-frame it if a better frame was found; repair the weak links the adversarial test exposed; correct the claims the empirical check caught; respect the premise map; absorb the abductive reading; reckon with what the genealogical analysis surfaced. Weight diagnostics by their stated rationale and trust level; treat low-trust diagnostics with appropriate skepticism.
>
> The diagnostics **inform** your answer — they do not all have to **appear** in it. Produce a single decisive answer that has silently absorbed these lenses, not a tour of them. Do not hedge into an everything-answer that names every caveat and commits to nothing.

## A.7 Quality gate (v0 rules)

```
for each diagnostic:
    if status != "ok":            -> drop (reason: empty/malformed)
    if self_confidence == "low":  -> admit, trust="low"
    if tool_id in {abductive, genealogical}:
        if redundant_with(output, baseline):  -> drop (reason: redundant)
    else:                         -> admit, trust="high"

sanity-check baseline before step 5; if baseline fails -> regenerate once, else abort to single-call fallback
```

`redundant_with` is a cheap similarity/novelty check (v0: a lightweight model call or embedding distance threshold; tune against the eval).

## A.8 Build order

1. The hardcoded vertical slice: baseline + two consumer tools (adversarial, empirical) + naive synthesis, on one real prompt, read against a bare single call. No orchestrator yet — hardcode the routing.
2. The A/B eval harness on a dozen real prompts, with per-tool instrumentation.
3. Develop synthesis against real failures observed in (1)–(2).
4. The quality gate, once a diagnostic has returned garbage in practice.
5. The full six-tool box with charters, and hand routing to the orchestrator.
6. Layer in the guard/override/discretion routing for the empirical tool.

Each step makes the next concrete instead of speculative.
