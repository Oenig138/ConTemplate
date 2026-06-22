# ConTemplate — Findings (v0 informal eval)

*Recorded 2026-06-22. Hand-run A/B evaluation, not the systematic harness in
`eval/`. Small n; treat as directional, not conclusive.*

## What was tested

The central claim (concept doc §8): **a structured multi-pass interrogation of
one cheap model's output beats that same model's single pass**, at trivial
cost. Worker model: **DeepSeek V4-Pro** via OpenRouter, Pro tier for
baseline/orchestrator/synthesis, Flash tier for diagnostics.

Two comparisons, both blind A/B:

1. **Harness vs its own baseline** — the bare single DeepSeek call (the thesis).
2. **Harness vs Claude Opus 4.8 High** — a frontier single call (the ceiling).

## Method

- Each prompt run once through the harness; the harness's own baseline (or the
  Opus answer) is the comparator.
- Both answers pasted into a blind A/B prompt (neutral "Answer A / Answer B"
  labels), order flipped deterministically per prompt to blunt position bias.
- **Five-judge panel:** the latest Grok, GPT (ChatGPT 5.5), Qwen, Claude, and
  Gemini. Only one label is pinned: **Judge B = ChatGPT 5.5**.
- A judge "win" is counted for the harness only after mapping its A/B verdict
  back through that prompt's randomized assignment.

### Methodological finding: one judge is position-biased
**Judge B (ChatGPT 5.5) answered "A" on 8 of 8 questions across both
comparisons** (p ≈ 0.4% by chance). It tracks *position*, not quality. Because
the harness was randomized across A/B, this bias split roughly evenly and the
randomization neutralized it — but Judge B's votes should be discarded.
Figures below are reported both with and without Judge B.

## Comparison 1 — Harness vs DeepSeek baseline

| Q | Topic | Harness pos | Harness | Single | Tie |
|---|-------|:-:|:-:|:-:|:-:|
| 1 | Roman collapse | A | 2 | 1 | 2 |
| 2 | Swedish nuclear | A | 4 | 1 | 0 |
| 3 | Scientific realism | B | 3 | 2 | 0 |
| 4 | Housing / inequality | A | 3 | 1 | 1 |
| 5 | Obesity | B | 4 | 1 | 0 |
| 6 | Ukraine war | B | 4 | 1 | 0 |
| **Total** | | | **20** | **7** | **3** |

- **All six questions won by the harness** on a majority/plurality.
- Decisive votes: **20/27 = 74% harness.**
- **Excluding the position-biased Judge B: 17–4–3, or 81% of decisive votes.**
  Three of the single-call's seven "wins" were Judge B's position artifact;
  obesity and Ukraine become clean 4–0 sweeps once it is removed.

### Routing vs. predicted tool value (from the audit records)

What the orchestrator actually selected, and whether it matched a domain
expert's prediction of which tools *should* matter:

| Q | Predicted high-value | Actually run | Match |
|---|---|---|---|
| 4 Housing | premise, adversarial, framing, **genealogical** | framing, premise, empirical, adversarial, ~~abductive (dropped)~~ | genealogical **missed**; empirical added; first-ever gate drop |
| 5 Obesity | **empirical**, adversarial, framing, premise | **empirical (1st)**, premise, framing, adversarial, abductive | near-perfect |
| 6 Ukraine | **framing**, adversarial, genealogical, empirical | premise, abductive, empirical, genealogical, framing | genealogical+framing+empirical ✓; **adversarial missed** |

The hits appear verbatim in the orchestrator's rationales — e.g. obesity's lead
reason was *"the model often hallucinates facts; empirical verification will
catch fabricated studies,"* and Ukraine's genealogical reason named
*"institutional realists favoring 'military capability' vs. liberal
institutionalists favoring 'alliance support.'"*

Tool-selection frequency across the six (high dial, ceiling 5): **premise 6/6,
adversarial 5/6, framing 5/6, empirical 5/6, abductive 4/6, genealogical 3/6.**

## Comparison 2 — Harness vs Claude Opus 4.8 High

| Q | Topic | Harness pos | Opus | Harness |
|---|-------|:-:|:-:|:-:|
| 1 | Roman collapse | B | 5 | 0 |
| 2 | Swedish nuclear | A | 4 | 1 |
| **Total** | | | **9** | **1** |

The lone harness vote was Judge B (its standing "A" bias landing on the harness
in Q2). **Excluding Judge B: Opus 8–0.** Opus beat the harness even on the
nuclear prompt — the harness's *strongest* category against its own baseline.

## Conclusions

1. **The thesis holds: the harness raises the floor.** Scaffolded DeepSeek beats
   bare DeepSeek ~74% (81% ex-B), winning all six prompts. The improvement is
   real and consistent.

2. **It does not raise the ceiling.** Scaffolded DeepSeek loses ~0–8 to frontier
   Opus 4.8. This confirms the architecture's own prediction (concept §2.2):
   five of six tools interrogate DeepSeek *with* DeepSeek, so a blind spot the
   model shares across passes survives every diagnostic. The synthesis step also
   runs on DeepSeek, whose weakest axis is exactly the discrimination synthesis
   demands (§5). The harness was never designed to make a cheap model
   frontier-grade.

3. **The edge tracks tool-applicability.** Margins are largest where external
   evidence can correct hallucination *and* multiple genuine frames compete
   (nuclear, obesity, Ukraine — empirical-heavy, 4–0/4–1). They are narrowest on
   canonical academic topics where the baseline is already near its ceiling
   (Rome: 2 ties; scientific realism: 3–2, and the orchestrator correctly ran no
   empirical there). "Reality gets a vote" is the best single predictor of a
   large margin so far.

4. **Routing largely matches expert intuition,** with two instructive misses
   (genealogical absent on housing; adversarial absent on Ukraine).

5. **The value proposition is quality-per-dollar, not frontier-matching.**
   Full 5-tool analytical runs cost **$0.015–$0.05** each (≈3–5× a single
   DeepSeek call; the cost edge holds because DeepSeek is a quality-per-dollar
   outlier). Adding a frontier model to a slot would raise the ceiling but
   defeats the pricing rationale and is out of scope.

## Limitations

- **n = 6** prompts (C1), **n = 2** (C2). Directional only.
- **All prompts are open-ended analytical essays** — the harness's home turf.
  The model's *strength zone* (coding, simple factual) is untested; that is
  where the harness might add noise or hurt.
- **Selectivity and the gate are untested.** At high dial the orchestrator ran
  4–5/6 tools every time and the gate admitted nearly everything (one drop
  ever). We have not seen the harness be selective or the gate prune at scale.
- **Caching ≈ 0** as structurally expected (each stage leads with a distinct
  charter; the parallel fan-out races); cost is output-dominated regardless.
- Judge-to-model mapping is recorded only for Judge B.

## Appendix — prompts (verbatim)

**Q1 — Roman collapse.** "The collapse of the Western Roman Empire is often
presented as the result of internal decadence, barbarian invasions, economic
decline, military overstretch, climate pressures, or some combination thereof.
Evaluate the major explanations proposed by historians over the last century and
determine which explanatory framework best accounts for the evidence. In your
answer, distinguish between proximate causes, structural causes, and
historiographical fashions. Explain not only what happened, but why different
generations of historians have preferred different explanations."

**Q2 — Swedish nuclear.** "Sweden is considering a major expansion of nuclear
power as part of its long-term energy strategy. Assume the goal is to achieve a
low-carbon, economically competitive, and politically stable electricity system
through 2050. Evaluate whether large-scale nuclear investment should be the
central pillar of Swedish energy policy. Consider economics, grid stability,
technological uncertainty, industrial competitiveness, climate goals, democratic
legitimacy, and opportunity costs. Conclude with a concrete recommendation."

**Q3 — Scientific realism.** "To what extent should scientific theories be
understood as descriptions of reality rather than predictive instruments?
Compare scientific realism, instrumentalism, structural realism, and Bayesian
approaches to theory choice. Using examples from quantum mechanics, evolutionary
biology, and cosmology, argue for the most defensible position. Address the
strongest objections to your conclusion."

**Q4 — Housing / inequality.** "During the past forty years, many advanced
economies have experienced rising housing costs, increasing wealth inequality,
and declining rates of family formation among younger generations. To what
extent can these trends be explained by monetary policy, land-use regulation,
demographic change, globalization, financialization, and technological change?
Evaluate the strongest competing explanations and identify which causal
mechanisms are most important. Conclude by recommending the policy interventions
most likely to improve affordability without creating larger distortions
elsewhere."

**Q5 — Obesity.** "The rapid rise in obesity across developed countries is often
attributed to ultra-processed foods, sedentary lifestyles, socioeconomic
factors, changes in the food environment, psychological stress, endocrine
disruption, and genetic predisposition. Evaluate the evidence for each
explanation and determine which combination of factors best accounts for current
obesity trends. In your answer distinguish between proximate mechanisms and
underlying causes, and explain which policy interventions are most likely to
have meaningful population-level effects."

**Q6 — Ukraine war.** "Was the outcome of the war in Ukraine primarily
determined by military capability, industrial capacity, political will, alliance
support, economic resilience, leadership quality, technological adaptation, or
demographic factors? Construct the strongest case for each major explanatory
framework and determine which offers the most convincing account of the
conflict's trajectory. Explain why analysts from different traditions often
reach different conclusions from the same events."
