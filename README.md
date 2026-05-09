# VERDICT — Modular Prompt Library

> **VERDICT**: *Value-aligned Evaluation and Reasoning for Domestic IoT Control Threats* — an LLM-mediated runtime arbiter for smart home automation, designed for submission to security venues (USENIX Security / CCS / NDSS / S&P).

Refactored from `prompt_template_v3.1.py` into composable modules so you can ablate, swap, and version-control individual pieces independently.

## Naming rationale

The system renders a **verdict** on each automation cascade — `ALLOW`, `DENY`, `INTERACT_USER`, `SCHEDULE_PLAN`, or `ADAPT` — based on a structured analysis of the predicted consequence chain against a user-intent specification (`I_spec`). The name was chosen because:

1. **Threat-model fit.** The work positions itself as a runtime monitor that *intercepts intent-misaligned automation cascades*, including those arising from third-party rule marketplaces (IFTTT, SmartThings community routines) and cross-rule interaction attacks (cf. iRuler, CCS '17). VERDICT is the literal output of that interception.
2. **Direct correspondence to a first-class output field.** The `decision_type` field IS the verdict; the framework name is not metaphorical.
3. **Security-venue cadence.** Punchy, non-mythological, no acronym-padding. Fits the lineage of ContexIoT, IoTGuard, HoMonit, AutoTap, Soteria, IRuler.

> **Before publishing:** confirm no name collision via Google Scholar + arXiv + ACM/IEEE Xplore search for `"VERDICT" smart home`, `"VERDICT" IoT`, `"VERDICT" automation`. Generic English-word system names are common; verify your slot.

## Directory layout

```
smart_home_mediator/
├── README.md                       <- this file
├── assemble.py                     <- composes modules into final prompts
├── prompts/
│   ├── 00_role_and_methodology.md  <- role + 3-stage process
│   ├── 01_key_definitions.md       <- surfaced from buried definitions in v3.1
│   ├── 02_principles.md            <- 4 principles (merged from v3.1's 5)
│   ├── 03_dsl_spec.md              <- action DSL (AFTER / DELAY / DENY)
│   ├── 04_output_schema.md         <- JSON output contract
│   └── 05_user_template.md         <- user prompt skeleton
├── examples/
│   ├── ex01_allow_redundant.md     <- ALLOW under redundancy (P1)
│   ├── ex02_schedule_temporal.md   <- SCHEDULE_PLAN with AFTER (P3)
│   ├── ex03_interact_deadlock.md   <- INTERACT_USER true deadlock (P2)
│   └── ex04_emergency_tradeoff.md  <- INTERACT_USER under emergency trade-off (P4)
└── project_plan.md                 <- 6-week research roadmap
```

## What changed vs. v3.1

| Change | Why |
|---|---|
| **P1 + P5 merged** into single "Default Allow" principle | They overlapped semantically and caused redundant reasoning |
| **P3 + P4 emergency paths consolidated** under P4 | v3.1 authorized emergency synthesis in two places with slightly different wording |
| **"Significant Goal Impairment" surfaced** to `01_key_definitions.md` | Was buried inside P1 — it's the single most decision-critical concept |
| **`AFTER(activity_change)` syntax surfaced** to definitions | Easy to miss when reading the DSL section alone |
| **Few-shot examples added** (4 canonical cases) | Zero-shot stability on this complex schema is poor |
| **`reasoning_summary` compressed** to one field | The 3-field version duplicated content already in `I_spec` and `gap_analysis` |
| **`interaction_prompt` semantics clarified** in schema | Disambiguates "interim plan" vs. "final plan in options" |

## Usage

```bash
# Default: full prompt with all 4 principles and all 4 examples
python assemble.py --task scenarios/scene_042.json > prompt.txt

# Ablation: drop principle P3 to measure its contribution
python assemble.py --task scenarios/scene_042.json --exclude-principles P3

# Ablation: zero-shot (no examples)
python assemble.py --task scenarios/scene_042.json --no-examples

# Ablation: drop the surfaced definitions block
python assemble.py --task scenarios/scene_042.json --no-definitions
```

The composer outputs a `(system_prompt, user_prompt)` pair ready for the API.
