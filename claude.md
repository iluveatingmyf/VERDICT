# CLAUDE.md — VERDICT Project Operating Manual

> This file is the persistent context for every Claude Code session in this repository.
> Read it fully before starting any task. Update it (via PR) whenever §1–§10 change.

---

## 0. Project at a Glance

**VERDICT** is a runtime mediation system for smart home automations. It intercepts trigger-action rule execution between platforms (SmartThings / Home Assistant) and physical devices, blocking unsafe interactions before they reach hardware. Its central novelty: **situation-aware** mediation in **multi-resident** households, where the safety of a rule depends not only on the rule itself but on *who* is doing *what*, *where* — and where rule-rule interactions go far beyond simple causal cascades.

- **Target venue**: USENIX Security / NDSS / IEEE S&P / ACM CCS (top-4 security)
- **Current phase (Week 1 of 6)**: IR design + statically-analyzable interaction patterns (P1–P4) + situation/cascade infrastructure on 20 hand-picked rules
- **Out of scope until later**: situation-dependent interaction patterns (P5–P9), full benchmark scale-up, LLM agent implementation, paper writing

If a task seems to fall outside the current phase, **ask the human before starting**.

---

## 1. Threat Model (READ THIS FIRST)

Every design decision must be traceable to this threat model. If a proposed change does not help defend against this adversary, flag it.

### 1.1 Primary Adversary
**Malicious automation provider** — a third party publishing rules to community marketplaces (HACS, IFTTT applet directory, SmartThings community, etc.). Realistic because:

- These marketplaces lack meaningful security review.
- Typical homes install 10–50 rules from non-official sources.
- Even vetted integrations can push malicious updates.

**Capabilities**:
- Publishes rules that individually pass casual inspection and any static linter.
- Publishes **multiple** rules whose composition produces emergent unsafe behavior through any of the 9 interaction patterns in §7.
- Reads VERDICT's public specs (LTL library, DSL grammar). **Adaptive / white-box attacker.**
- Cannot a priori observe runtime per-resident activity inference. This is VERDICT's information advantage — and a defense target (see §4.5).

### 1.2 Secondary Adversary
**Single compromised IoT device** — one low-privilege device (motion sensor, smart bulb, contact sensor) that has been firmware-compromised. Can inject false readings, modify its own metadata (`friendly_name` → prompt-injection vector), or deliberately craft sensor patterns that mislead the activity recognizer (see §7 P8). The "single" qualifier is load-bearing: cross-sensor consistency is part of VERDICT's defense.

### 1.3 Out of Scope (state explicitly in §3 of any paper draft)
- VERDICT mediator compromise
- Home Assistant core compromise
- Network-layer attacks (handled by TLS)
- Multi-device collusion
- Intimate-partner / insider threats (different problem; belongs at CHI, not security)

### 1.4 Adversary Goals (prioritized for benchmark coverage)
1. **Physical breach** — unlock door / disarm alarm in a vulnerable window
2. **Surveillance enablement** — leak occupancy / routine to attacker
3. **Denial of Service** — lock user out, frame as false alarm
4. **Resource exhaustion** — energy DoS, device lifetime attacks
5. **Inter-resident attack** — exploit one resident's routine to harm or surveil another (e.g., using a guest's occupancy pattern as a side channel against the primary resident; using a child's activity to trigger actions hostile to a parent)

Goal 5 is unique to multi-resident threat models and is a core differentiator. Benchmark must cover it.

### 1.5 Attack Mechanism × Goal Matrix

Goals (§1.4) describe *what* the attacker wants. Mechanisms (§7 interaction patterns + §8 attack patterns) describe *how*. The benchmark evaluates the cross product: every non-empty cell must have ≥1 scenario.

|                        | G1 Breach | G2 Surveil | G3 DoS | G4 Resource | G5 Inter-resident |
|------------------------|:---------:|:----------:|:------:|:-----------:|:-----------------:|
| AP1 single mal. rule   | ✓         | ✓          | ✓      | ✓           | ✓                 |
| AP2 multi-rule cascade | ✓         | ✓          | ✓      | ✓           | —                 |
| AP3 inter-resident exp.| —         | ✓          | —      | —           | ✓                 |
| AP4 sensor spoof       | ✓         | —          | ✓      | —           | —                 |
| AP5 metadata injection | varies    | varies     | varies | —           | —                 |
| AP6 TOCTOU race        | ✓         | ✓          | —      | —           | —                 |
| AP7 implicit-assump.   | ✓         | ✓          | —      | ✓           | ✓                 |
| AP8 activity-infer mfg.| ✓         | ✓          | —      | —           | ✓                 |

AP definitions in §8.3. Statically-detectable (Week 1): AP1, AP2. Situation-dependent (Week 2+): AP3, AP6, AP7, AP8. LLM-layer: AP5.

### 1.6 Trusted Computing Base
- **Trusted**: mediator code, LTL specifications, static interaction analyzer, plan validator, HA core, ≥2 independent sensing modalities, activity recognizer output *labels* (treated as oracle in benchmark; subject to integrity defense at deploy — see §4.5).
- **Untrusted**: third-party rules, single-sensor readings, device metadata.
- **Partially trusted**: LLM agents — trusted to *attempt* alignment, but their output must pass the symbolic plan validator before execution. **LLM is never on the safety-critical path.**

### 1.7 Security Property (formal claim)
> Given an LTL safety specification Φ — where Φ may reference situation predicates evaluated against per-resident activity timelines and world state — and a stream of trigger events, VERDICT guarantees that no action sequence violating Φ is executed, provided (i) at most one sensing modality is compromised at any time, (ii) the symbolic plan validator is sound w.r.t. Φ, (iii) the activity recognizer's per-resident labels are within an assumed error bound α (evaluated empirically in §evaluation), and (iv) the situation integrity defense (§4.5) flags inputs that fall outside the assumed integrity envelope.

LLM does not appear in this guarantee. LLM contributes to *utility* (synthesizing alternatives when the symbolic layer rejects a plan), not *safety*.

---

## 2. Architecture & Hot Path Discipline

### 2.1 Three-rate neuro-symbolic design

```
[INSTALL TIME — once per rule-set change]
  raw rules (Groovy / YAML / IFTTT JSON)
       ↓ parser
  IR (unified, capability-based)
       ↓ static interaction analyzer  (P1–P4 patterns; §7)
  Interaction Graph G_int  (cached on disk)
       ↓ LTL pre-check (situation-independent edges)
  annotated G_int with dangerous edges marked

[BACKGROUND — continuous, low frequency, cheap]
  Activity Recognizer  (oracle in benchmark; module at deploy)
  Input:   rolling window of sensor events
  Output:  per-resident activity timeline + role tag
  Rate:    every ~30s; near-zero LLM cost
       ↓
  Situation Integrity Monitor  (see §4.5)
       checks recognizer output for tampering signals

[RUNTIME — per event, ~100–500/day for a typical home]
  trigger event e
       ↓ assemble Situation s = (residents' timelines, world state, e)
       ↓ G_int subgraph lookup           (μs)
       ↓ situation-dependent pattern check (P5–P9; §7)
       ↓ LTL evaluation Φ(s)             (ms; situation predicates resolved)
       │
       ├── PASS (~95% of events) → ALLOW, execute
       │
       └── FAIL (~5% of events) → invoke LLM agents
                                       ↓
                               Agent A (Intent Inference)     → I_spec
                               Agent B (Risk Assessor)        → impact tags on G_int
                               Agent C (Plan Synthesizer)     → DSL plan
                               Agent D (Adversarial Verifier) → red-team check
                                       ↓
                               Plan Validator (symbolic; re-checks Φ(s))
                                       ↓
                               execute / interact_user / deny
```

### 2.2 Hot-path commandments (non-negotiable)
1. **LLM is NEVER on the safety-critical path.** Symbolic layer makes the safety decision; LLM only proposes alternatives.
2. **Static interaction analysis runs ONCE per rule-set change**, not per event. Runtime is a `G_int` query, not a re-analysis.
3. **Activity recognition runs in the BACKGROUND**, not at trigger time. Trigger time only assembles a Situation from already-inferred labels.
4. **Emergency protocols are pure-symbolic.** L1 life-safety events (smoke, CO) never wait for LLM.
5. **Cost target**: ≤ $15/month per home in LLM API costs. If a design pushes above $30/month, redesign before implementing.

---

## 3. Situation & Activity Model

This section is the conceptual core of VERDICT. The same rule can be safe or unsafe depending on the situation in which it fires; conversely, a high-risk rule may be precisely what the user wants in the right situation. VERDICT's job is to evaluate (rule × situation × other rules in the rule set), not rule alone.

### 3.1 Three layers (do not conflate)

| Layer | Content | Granularity | Source at runtime | Source at benchmark |
|-------|---------|-------------|-------------------|---------------------|
| L1: Raw event stream | timestamped sensor events | event-level | sensor bus | CASAS/ARAS sensor log |
| L2: Activity label | semantic activity per resident | activity-level (typed, with begin/end timestamps) | activity recognizer (background) | dataset ground-truth annotation (oracle) |
| L3: Situation | assembled context at a trigger | composite | constructed at trigger time | given as benchmark input |

Activity is a *component* of Situation, not synonymous with it.

### 3.2 Situation schema (multi-resident, canonical)

```python
@dataclass(frozen=True)
class ActivityEpisode:
    activity_type: str          # e.g. "Eating", "Sleeping", "Meal_Preparation"
    begin: datetime
    end: datetime | None        # None = ongoing
    location: str | None        # e.g. "kitchen", "bedroom"; None if unknown

@dataclass(frozen=True)
class Resident:
    id: str                     # "R1", "R2"
    role: str                   # closed enum, see §3.5
    activity_timeline: list[ActivityEpisode]   # ordered, recent window
    current_location: str | None

@dataclass(frozen=True)
class Situation:
    residents: list[Resident]                  # ≥1
    world_state: dict[str, "Value"]            # entity_ref → current value; single source of truth
    triggering_event: "Event"
    timestamp: datetime
    confidence: dict[str, float] = field(default_factory=dict)
                                # activity recognizer confidence per resident
```

Design rules:
- **World state is single-valued.** The house has one truth about whether the front door is locked, regardless of how many residents live there.
- **Each resident has their own timeline.** Conflating into a single timeline destroys the cross-resident reasoning VERDICT exists to do.
- **`role` is a closed enum.** Adding a new role requires updating §3.5 and re-validating LTL constraints that quantify over roles.
- **`location` is coarse-grained.** Use room labels, not coordinates. Constraint predicates reason at room level.

### 3.3 Situation modality: benchmark-given vs runtime-constructed

- **Benchmark / evaluation**: Situation is *given* — full per-resident activity timeline + world state + triggering event are ground-truth annotated, derived from public datasets (§9.2). Evaluation is deterministic and reproducible.
- **Runtime / deployment**: Activity is inferred continuously by a background recognizer; world state is read from the device bus; the triggering event arrives from the rule engine. The mediation pipeline composes these into a `Situation` value at trigger time.

Paper §3 (system model) writes this distinction explicitly.

### 3.4 Activity recognizer treatment

We **do not implement** an activity recognizer. Activity recognition is well-studied; we treat it as an external module.

- **In the benchmark**: use dataset ground-truth activity annotations as an oracle recognizer.
- **In the paper**: report results both with the oracle and under injected label noise (α = 5%, 10%, 20% mislabeled episodes) to characterize sensitivity to recognizer error.
- **Justification text** for §3 of the paper: "We assume an external activity recognition module and treat its output as input to VERDICT. Recognizer accuracy is orthogonal to our contribution; we evaluate robustness to recognizer error in §X.Y, and against adversarial manipulation of the recognizer in §X.Z (see §4.5)."

### 3.5 Target resident configurations (benchmark must cover all 3)

| ID | Configuration | Residents | Why it matters |
|---|---|---|---|
| **C1** | Elderly + caregiver | `elderly` + `caregiver` | Role asymmetry; constraints often single-resident-targeted |
| **C2** | Couple / cohabitants | 2× `primary_adult` (or `cohabitant`) | Role symmetry; conflicting preferences |
| **C3** | Parent + child | `primary_adult` + `child` | Control asymmetry; child cannot consent to many actions |

Closed `role` enum (Week 1): `primary_adult`, `elderly`, `caregiver`, `child`, `guest`, `cohabitant`. Adding a role requires PR + paper-section justification.

---

## 4. LTL Constraint Framework

Constraints are written **once, statically**, and they generalize across situations by **referencing situation predicates** rather than enumerating situation instances. This is the design that makes the system tractable.

### 4.1 Constraint structure

A constraint is a guarded LTL formula:

```yaml
constraint:
  id: "C-elderly-fall-risk"
  description: "Do not extinguish hallway lights while an elderly resident is walking there at night"
  ltl: |
    □ (
      (∃ r ∈ residents:
         r.role = "elderly"
         ∧ r.current_location = "hallway"
         ∧ r.latest_activity.type ∈ {"Walking", "Bed_to_Toilet"})
      ∧ time_of_day ∈ ["22:00", "06:00"]
      →
      ¬ (action.capability = "light"
         ∧ action.target_location = "hallway"
         ∧ action.delta_illuminance < -50)
    )
  severity: "L2_high"     # one of L1_life_safety, L2_high, L3_medium, L4_low
  grounded_in:            # see §4.3
    - "cve_class:iot_lighting_fall_hazard"
    - "empirical_pattern:hallway_motion_light_overlap"
```

### 4.2 Closed predicate vocabulary (constraints may only reference these)

| Predicate kind | Examples |
|---|---|
| Per-resident | `r.role`, `r.current_location`, `r.latest_activity.type`, `r.latest_activity.duration_min` |
| Quantifier | `∃ r ∈ residents: P(r)`, `∀ r ∈ residents: P(r)` |
| World state | `world_state[entity_ref].value`, `world_state[entity_ref].changed_within_min` |
| Action | `action.capability`, `action.target_location`, `action.delta_*` |
| Temporal | `time_of_day`, `day_of_week`, `□`, `◇≤t`, `U` |

Adding a new predicate kind requires PR + update to this table.

### 4.3 Constraint grounding (every constraint must cite at least one source)

To survive reviewer scrutiny ("where do these constraints come from?"), every constraint cites at least one:

- **`cve_class:*`** — derived from a documented IoT incident class (CVE database, vendor advisory).
- **`empirical_pattern:*`** — mined from real-rule corpus (§10) as a frequent invariant.
- **`formal_property:*`** — established safety property from prior work (Soteria, IoTGuard, IoTSafe).

No "common sense" constraints. Every constraint traceable.

### 4.4 LTL fragment

Bounded safety (`□ φ`) and bounded liveness (`□(φ → ◇≤t ψ)`) only. Decidable, model-checkable, aligned with prior IoT safety work.

### 4.5 Beyond LTL: Situation Integrity Defense Layer

LTL evaluates a formula against *given* situation predicates. If those predicates are themselves manipulated (e.g., activity recognizer fooled into labeling a burglary as "Cooking"), LTL provides no protection. This is the gap that §7 P8 / P9 attacks exploit and that AP8 targets.

**Situation Integrity Monitor** is a separate defensive layer with its own contract:

- **Input**: activity recognizer output stream, sensor data stream, world state history
- **Output**: boolean `integrity_ok` + anomaly score per resident-activity
- **Mechanism** (any subset, evaluated empirically):
  - **Cross-modality consistency**: e.g., declared activity = "Cooking" should correlate with stove/microwave/refrigerator usage events
  - **Temporal plausibility**: rapid implausible activity transitions flagged
  - **Per-resident behavior profile**: significant deviation from established baseline flagged
  - **Sensor signature anomaly**: motion patterns that match no known human activity but match adversarial attack templates flagged

When integrity check fails, the system **does not silently degrade to "no constraint"** — it escalates: either fall back to a conservative all-residents-present-and-vulnerable assumption (over-protect), or invoke LLM agents with the situation marked unreliable. Specific fallback policy is a design parameter (`integrity_failure_policy`) documented per deployment.

**Paper positioning**: this layer is what makes VERDICT's situation-awareness defensible against adaptive attackers. Without it, the system is trivially defeated by AP8. With it, the formal claim in §1.7 condition (iv) holds.

**Week 1 status**: the *interface* of this layer is specified; implementation deferred to Week 3+. Don't build it now.

---

## 5. Intermediate Representation (IR) for Rules

The IR is the technical contract that decouples rule source from analysis. Interaction analyzer, LTL checker, and plan validator all consume IR — none touch raw Groovy / YAML / JSON.

### 5.1 Canonical schema

```yaml
rule:
  id: "<source>_<short_desc>"            # e.g. "iotbench_official_smart_light"

  source:
    platform: "smartthings" | "ha" | "ifttt"
    origin: "iotbench_official" | "iotbench_third" | "iotbench_malicious"
          | "smartappzoo" | "ha_blueprint" | "ifttt_recipe"
    raw_path: "datasets/.../foo.groovy"
    popularity: 1234 | null
    description_oneliner: "Turn on light when motion detected at night"

  intent_nl: "<one-sentence human summary in English>"

  triggers:                              # list = OR
    - capability: "motion"
      entity_ref: "$motion_1"            # placeholder; bound to situation at scenario time
      event: "active"
      params: {}

  conditions:                            # list = AND; [] if none
    - capability: "illuminance"
      entity_ref: "$illuminance_1"
      predicate: "less_than"             # equals | not_equals | less_than | greater_than | in_range
      value: 50

  actions:                               # list = sequential
    - capability: "switch"
      entity_ref: "$switch_1"
      command: "on"
      params: {}
      delay_ms: 0

  derived:                               # parser auto-fills; never hand-edit
    capabilities_read: ["motion", "illuminance"]
    capabilities_written: ["switch"]
    state_changes:
      - entity_ref: "$switch_1"
        from: "*"
        to: "on"

  notes:                                 # human-facing only
    interaction_pattern: "P1"            # one of P1–P9 (§7); P1–P4 expected in Week 1
    security_relevant: false
    why_picked: "Typical P1 sink; cascade entry point in motion-light corpus"
```

### 5.2 IR design rules
- **Capability-based, not entity-based.** `$lock_1`, never `light.kitchen_main`. Binding to real entities happens at scenario instantiation (§8).
- **Capability vocabulary is closed** (see §6).
- **Drop, don't fudge.** If a rule uses Groovy/Jinja complexity beyond this schema, drop it and log to `docs/unsupported_rules.md`. Do not paper over with simplifications.
- **`derived` is deterministic.** Computed by parser; never hand-edited.
- **IR is rule-level, not pair-level.** Interaction patterns (§7) emerge from analysis *over* the IR corpus; they are not recorded in IR itself except as informational tags in `notes`.

---

## 6. Standardized Capability Vocabulary

Only these 12. Adding a new one requires PR + human approval + re-scan of existing IR files.

| Capability        | Common events / commands               | Notes                              |
|-------------------|-----------------------------------------|------------------------------------|
| `switch`          | on, off, set_level                      | Smart plug, generic on/off         |
| `light`           | on, off, set_level, set_color           | Subtype of switch with extras      |
| `motion`          | active, inactive                        | Read-only                          |
| `presence`        | present, not_present                    | Read-only                          |
| `contact`         | open, closed                            | Door / window sensor               |
| `lock`            | lock, unlock                            | **Security-critical**              |
| `temperature`     | set_temperature (thermostat)            | Sensor: read-only; thermostat: write |
| `illuminance`     | (read-only)                             | Lux sensor                         |
| `smoke_detector`  | clear, detected                         | **L1 safety**                      |
| `co_detector`     | clear, detected                         | **L1 safety**                      |
| `notification`    | send_notification                       | params: `{message, target}`        |
| `time`            | at, between                             | params: `{time}` or `{start, end}` |

Capability frequency in real corpora (approximate; Surbatovich WWW'17, Yu SenSys'21):
```
switch ~40%   notification ~20%   motion ~15%   presence ~12%
contact ~10%  lock ~8%            temperature ~7%   smoke+co ~3%
```
**Sampling target**: each of these top-8 capabilities appears ≥2 times in the 20-rule starter corpus.

---

## 7. Rule Interaction Patterns (P1–P9)

The full taxonomy of how two or more rules can interact unsafely. Cascade (P1–P3) is one category among five. Patterns differ in (a) whether they are statically detectable from IR alone, and (b) whether they require situation context.

| ID | Category | Pattern | Statically detectable? | Needs situation? |
|----|----------|---------|------------------------|------------------|
| **P1** | Causal | Sink | yes | no |
| **P2** | Causal | Linear cascade A→B→C | yes | no |
| **P3** | Causal | Fan-out | yes | no |
| **P4** | State-sharing | Race write (conflicting OR interfering values) | yes | partial |
| **P5** | State-sharing | TOCTOU read (rule reads a value freshly written by another rule that did not trigger it) | no | yes |
| **P6** | Temporal | Order-dependent sequence (safe only if R₁ executes before R₂) | partial | yes |
| **P7** | Semantic | Implicit assumption violation (R₁ assumes state X without checking; R₂ violates X) | no | yes |
| **P8** | Inference | **Activity inference manipulation** (rule deliberately produces sensor patterns to mislead the activity recognizer) | no | yes |
| **P9** | Inference | **Resident misidentification** (rule produces patterns that cause one resident's activity to be attributed to another) | no | yes |

### 7.1 Causal patterns (P1–P3)

Define the static **interaction graph** `G_int`:
> Edge `A → B` exists in `G_int` iff `A.derived.capabilities_written ∩ B.derived.capabilities_read ≠ ∅` AND some state-change in `A.derived.state_changes` can satisfy a trigger predicate of `B`.

- **P1 Sink**: rule R, no outgoing edges in `G_int`.
- **P2 Linear cascade**: path of length ≥2 in `G_int`.
- **P3 Fan-out**: node with out-degree ≥2 in `G_int`.

These are fully covered by `verdict/static_analysis/cascade_builder.py` (Week 1).

### 7.2 State-sharing patterns (P4–P5)

- **P4 Race write**: two rules write the same `(entity_ref, capability)` under overlapping trigger conditions. Subtypes: **conflicting** (opposite values) or **interfering** (different parameters that compose dangerously, e.g., one sets brightness 100, another sets brightness 10 within seconds). Statically detectable from IR; severity assessment may need situation.
- **P5 TOCTOU read**: R₁ reads a value as a *condition*, R₂ writes that value, the temporal interleaving determines outcome. Edge does NOT exist in causal `G_int` because R₁ is not triggered by R₂. Requires runtime situation + event ordering. **Week 2+ analyzer.**

### 7.3 Temporal patterns (P6)

- **P6 Order-dependent sequence**: two rules whose actions are safe in one order but unsafe in the reverse. Example: "disarm alarm" → "unlock door" is fine; reverse triggers a false alarm. Partial static detection (via action-precondition analysis); confirmation needs situation.

### 7.4 Semantic patterns (P7)

- **P7 Implicit assumption violation**: a rule R₁ assumes the world is in some state X without writing X as a condition. R₂ may take the world out of state X without R₁ knowing. Mining these assumptions requires either NL processing of rule descriptions or human annotation. **Not statically reliable; situation needed.**

### 7.5 Inference patterns (P8–P9) — paper-defining

These attacks target the *activity recognizer's input space*, not the rule graph or world state directly.

- **P8 Activity inference manipulation**: malicious rule M causes a sensor pattern that, when seen by the recognizer, induces an incorrect activity label. The attacker's goal is to make subsequent LTL evaluation use the wrong situation. Example: trigger fake motion in dining room to make recognizer label "Eating", thereby suppressing constraints that fire only during "Sleeping".
- **P9 Resident misidentification**: similar to P8 but specifically attributes activity to the wrong resident, exploiting cases where the recognizer cannot perfectly distinguish residents from sensor signatures alone.

Both are detected by the situation integrity defense layer (§4.5), not by `G_int` or LTL alone.

### 7.6 Week 1 scope vs full scope

| Week 1 (`cascade_builder.py`) | Week 2–3 (new analyzers) |
|-------------------------------|--------------------------|
| P1, P2, P3 (full)             | P4 (full), P5, P6 (partial), P7 |
| P4 (subset: conflicting only) | P8, P9 (via §4.5)               |

Starter 20-rule corpus must contain examples of P1–P4 (4 each = 16, plus 4 of "uncategorized" pending P5–P9 work). Do not try to manually construct P8/P9 examples in Week 1 — they require situation context to make sense.

---

## 8. Benchmark Composition Protocol

A benchmark scenario is the unit of evaluation. Scenarios are **systematically generated**, not hand-curated.

### 8.1 Scenario tuple

```
Scenario = (
  rule_subset,              # k rules from IR corpus (typically k=5–10)
  situation_template,       # episode-derived situation (§3.2)
  capability_binding,       # map from IR $-placeholders to situation entity_refs
  attack_pattern,           # one of: none | AP1 ... AP8  (see §8.3)
  ground_truth_label        # safe / unsafe (+ which constraint violated)
)
```

### 8.2 Generation procedure
1. Sample `k` rules from the IR corpus respecting interaction pattern + capability balance.
2. Sample a situation template from the episode pool (§10.2).
3. Bind IR `$-placeholders` to situation entities by capability match (auto where unambiguous; manual where not).
4. For adversarial scenarios: inject one attack from §8.3.
5. Label by running the *intended-behavior oracle* — a hand-written reference judge — over (scenario × constraint library).

### 8.3 Attack patterns (AP1–AP8)

| Code | Pattern | Targets adversary goal | Hits interaction pattern | Phase |
|------|---------|------------------------|--------------------------|-------|
| AP1 | Single malicious rule injection | G1–G4 | P1–P3 | Week 2 |
| AP2 | Multi-rule cascade injection (emergent) | G1–G4 | P2, P3 | Week 2 |
| AP3 | Inter-resident exploit (uses C1/C2/C3 asymmetry) | G5 | P4, P7 | Week 3 |
| AP4 | Sensor spoof (single compromised device) | G1, G3 | P8 input | Week 3 |
| AP5 | Metadata prompt injection (via device `friendly_name`) | varies | LLM-layer | Week 4 |
| **AP6** | **TOCTOU race window** | G1, G2 | **P5** | Week 3 |
| **AP7** | **Implicit-assumption violation** | G1, G2, G4, G5 | **P7** | Week 3 |
| **AP8** | **Activity inference manipulation** | G1, G2, G5 | **P8, P9** | Week 3 |

### 8.4 Target benchmark size
```
30 situations × 8 rule_subsets × 5 attack_patterns ≈ 1,200 scenarios
```
- 30 situations distributed evenly across C1, C2, C3 (10 each).
- Within each configuration, episodes drawn from ≥2 multi-resident datasets to avoid single-source bias.
- 5 attack patterns sampled from AP1–AP8 per scenario family (full matrix coverage is too large; coverage report in §evaluation).

---

## 9. Datasets

Located under `datasets/` (**gitignored** — never commit; re-clone if missing).

### 9.1 Rule corpora (logic)

| Dataset       | Path                                  | Upstream                                          | Use                              |
|---------------|---------------------------------------|---------------------------------------------------|----------------------------------|
| IoTBench      | `datasets/IoTBench-test-suite/`       | github.com/IoTBench/IoTBench-test-suite           | 8 official + 4 malicious picks   |
| SmartAppZoo   | `datasets/SmartAppZoo/`               | github.com/SmartAppZoo/SmartAppZoo                | 4 third-party Groovy picks       |
| HA Blueprints | `datasets/awesome-ha-blueprints/`     | github.com/EPMatt/awesome-ha-blueprints           | 4 modern YAML picks              |

**IFTTT is NOT used in starter corpus.** Its expressive power (no conditions, single trigger+action) is too weak for interaction prototyping. May be used later for §2 motivation popularity statistics in the paper.

### 9.2 Activity corpora (situation timelines, multi-resident)

| Dataset                          | Path                                  | Notes                                                    |
|----------------------------------|---------------------------------------|----------------------------------------------------------|
| CASAS Twor                       | `datasets/casas_twor/`                | 2 residents, per-resident activity labels                |
| ARAS House A & House B           | `datasets/aras_house_a/`, `_b/`       | 2 residents each, minute-level dual-label                |
| CASAS Multi-resident ADL         | `datasets/casas_multi_adl/`           | Smaller; designed for multi-resident                     |

Acquisition requires registration (CASAS) or direct download (ARAS). Document instructions in `docs/dataset_setup.md`. Do not commit data.

### 9.3 Re-clone command (rule corpora only — activity corpora need registration)
```bash
mkdir -p datasets && cd datasets
git clone --depth 1 https://github.com/IoTBench/IoTBench-test-suite
git clone --depth 1 https://github.com/SmartAppZoo/SmartAppZoo
git clone --depth 1 https://github.com/EPMatt/awesome-ha-blueprints
```

### 9.4 Sensor → capability mapping
A single `verdict/data/sensor_capability_map.yaml` file maps CASAS / ARAS sensor IDs to standardized capabilities (§6). Written once, used by the episode extractor for all datasets.

---

## 10. Sampling Methodology

### 10.1 Rule sampling (starter corpus: 20 rules)
Priority order:
1. **Interaction pattern diversity** > device diversity. For Week 1: 4 each of P1, P2, P3, P4 = 16 rules. Plus 4 "uncategorized but representative" rules to be classified as P5–P9 candidates in Week 2.
2. **Capability coverage**: each top-8 capability appears ≥2 times.
3. **Security relevance**: ≥12 of 20 involve `lock`, `smoke_detector`, `co_detector`, `presence`, `contact`, or `notification`.
4. **Source mix**: 8 IoTBench-official + 4 IoTBench-malicious + 4 SmartAppZoo + 4 HA.
5. **Complexity ceiling**: < 200 lines (Groovy) or < 100 lines (YAML).

Record `why_picked` in IR `notes`. Rejected candidates → `docs/unsupported_rules.md` with reason.

Output: `verdict/data/ir/<origin>_<short_slug>.yaml`.

### 10.2 Episode sampling (starter situation pool: 30 episodes)
1. Across C1 / C2 / C3 configurations — 10 episodes each.
2. Within each configuration, draw from ≥2 datasets to avoid single-source bias.
3. Episode duration: **30–90 minutes** (the activity window surrounding the trigger).
4. Triggering event placed mid-timeline (not at endpoints).
5. ≥1/3 of episodes contain ≥2 simultaneously active residents (multi-resident interaction is the contribution).

Record per episode: `derived_from` (dataset + episode timestamp range), `household_meta` (n_residents, layout, roles), brief textual description.

Output: `verdict/data/situations/<config>_<slug>.yaml`.

---

## 11. Repository Layout

```
verdict/
├── CLAUDE.md                          # this file
├── README.md                          # human-facing project overview
├── pyproject.toml                     # ruff + pytest + mypy config
├── .gitignore                         # excludes datasets/, .venv/, __pycache__/
├── datasets/                          # gitignored
├── verdict/
│   ├── ir/
│   │   ├── schema.py                  # pydantic models for IR
│   │   └── parsers/                   # groovy_parser.py, yaml_parser.py
│   ├── situation/
│   │   ├── schema.py                  # Situation, Resident, ActivityEpisode
│   │   ├── extractor.py               # CASAS/ARAS episode → situation template
│   │   └── instantiator.py            # bind IR placeholders to situation entities
│   ├── static_analysis/
│   │   ├── cascade_builder.py         # P1–P3, partial P4 (Week 1)
│   │   ├── race_detector.py           # P4 full (Week 2)
│   │   ├── toctou_detector.py         # P5 (Week 3)
│   │   ├── order_analyzer.py          # P6 (Week 3)
│   │   ├── assumption_miner.py        # P7 (Week 3)
│   │   └── plan_validator.py
│   ├── integrity/                     # situation integrity defense (§4.5; Week 3+)
│   │   ├── monitor.py
│   │   └── checks/                    # cross_modality.py, temporal.py, profile.py
│   ├── ltl/
│   │   ├── language.py                # LTL AST + bounded checker
│   │   ├── predicates.py              # closed predicate vocabulary (§4.2)
│   │   └── library/                   # seed constraint files
│   ├── agents/                        # Week 4+ — empty for now
│   │   ├── a_intent/
│   │   ├── b_risk/
│   │   ├── c_synthesizer/
│   │   └── d_verifier/
│   ├── benchmark/
│   │   ├── compose.py                 # scenario generator (§8)
│   │   ├── attacks/                   # AP1–AP8 attack injection modules
│   │   └── oracle.py                  # ground-truth labeling
│   ├── data/
│   │   ├── ir/                        # 20 starter IR yaml files
│   │   ├── situations/                # 30 starter situation templates
│   │   ├── constraints/               # seed LTL constraints (~10–20)
│   │   └── sensor_capability_map.yaml
│   └── pipeline.py                    # top-level orchestrator
├── tests/                             # mirrors verdict/ structure
└── docs/
    ├── dataset_setup.md               # how to acquire CASAS / ARAS
    ├── unsupported_rules.md           # dropped rules + reasons
    └── decisions/                     # ADRs for major design choices
```

Note: only `cascade_builder.py`, `schema.py` (both ir and situation), `extractor.py` skeleton, `groovy_parser.py`, `yaml_parser.py` should have substantive content by end of Week 1. Other files are empty placeholders.

---

## 12. Engineering Conventions

- **Python**: 3.11+, type hints required, `ruff format` + `ruff check`, `mypy --strict`.
- **Schema files**: pydantic v2 dataclasses; YAML for human-authored, JSON for machine-generated.
- **IR / situation files**: one item per file, naming `<origin>_<slug>.yaml` or `<config>_<slug>.yaml`.
- **Commits**: imperative mood; group related changes; **never commit `datasets/`**.
- **PRs**: one logical purpose per PR; description references CLAUDE.md sections.
- **Tests**: pytest; mirror module structure under `tests/`. Unit tests on parsers, cascade builder, situation extractor; integration test on end-to-end pipeline.
- **New dependencies**: flag explicitly in PR description with justification.

---

## 13. Working Style — How to collaborate with the human

The human is the **research lead**; Claude Code is the **engineering executor**. Roles are stable.

### Decide autonomously
- File layout details, helper function structure, test cases, formatting.
- Refactoring for clarity, fixing obvious bugs.
- Choosing between equivalent libraries (note choice in PR).
- How to implement a clearly-specified task.

### Ask BEFORE doing
- Anything that changes the IR schema (§5) or Situation schema (§3.2).
- Anything that adds a capability (§6), resident role (§3.5), predicate kind (§4.2), interaction pattern (§7), or attack pattern (§8.3).
- Anything that touches threat model (§1) or security property (§1.7).
- Adding / removing datasets (§9).
- Adding new resident configurations (§3.5).
- Scope-creep: tasks outside current phase (§0, §14).

### Flag but don't block
- Rules that don't fit IR cleanly → log to `docs/unsupported_rules.md` and proceed.
- Cost / performance estimates violating §2.2 commandments → flag in PR.
- Inconsistencies between this file and code → flag and propose fix.

### PR description template
```
## What
<one paragraph>

## Why
<which CLAUDE.md section(s) this serves>

## Decisions made autonomously
<list>

## Decisions deferred to human review
<list, or "none">

## Unsupported / dropped items
<reference to docs/unsupported_rules.md entries>
```

---

## 14. Current Phase Tasks (Week 1)

Execute in order. **STOP and request review after each numbered task** unless explicitly told to chain. Week 1 focuses on **statically-detectable patterns (P1–P4)** and **infrastructure**. P5–P9 and the integrity layer (§4.5) are Week 2–3.

1. ✅ Scaffold repository layout (§11). Create empty package skeleton, `pyproject.toml`, `.gitignore`, `README.md` stub. Create empty placeholder modules for Week 2+ analyzers and the integrity layer — they exist as stubs only.
2. ⏳ Clone rule-corpus datasets to `datasets/` (§9.3). Add `docs/dataset_setup.md` documenting how to acquire CASAS Twor + ARAS + CASAS Multi-resident ADL (registration required; the human will perform the acquisition).
3. ⏳ Implement minimal Groovy regex scanner: extract `subscribe(...)` triggers and common command calls (`*.on() / .off() / .lock() / .unlock() / .setLevel() / .setColor() / sendPush() / ...`). 70% coverage is sufficient — drop the rest with logging.
4. ⏳ Survey IoTBench official + malicious; produce a candidate list of **12 rules** with interaction pattern tags (P1–P4 only; flag any P5–P9 candidates for Week 2). PR with the list as a Markdown table; do not yet generate IR yaml.
5. ⏳ Survey SmartAppZoo Github third-party; pick **4 candidates**. Same format as task 4.
6. ⏳ Survey HA blueprints; pick **4 candidates**. Same format.
7. ⏳ After human approves the 20-rule candidate list: generate IR YAML drafts. Mark `# TODO` where automated extraction was uncertain. Output to `verdict/data/ir/`.
8. ⏳ Implement `verdict/situation/schema.py` (pydantic models per §3.2) and `verdict/situation/extractor.py` skeleton: parse CASAS-format sensor logs when data is provided, extract activity episodes with begin/end timestamps and resident IDs. Defer real episode extraction until datasets are present.
9. ⏳ Implement `verdict/static_analysis/cascade_builder.py`: compute `G_int` (P1–P3 edges + P4 conflicting-write subset) from the 20 IR rules using the edge definition in §7.1. Output DOT or Mermaid visualization to `docs/interaction_graph_week1.svg`.
10. ⏳ Report back in a single summary PR: pattern coverage table (P1–P4 counts), capability coverage table, unsupported-rule list, interaction graph image, list of rules flagged as P5–P9 candidates for Week 2.

**Out of scope this week**: LLM agents, LTL checker implementation, scenario generation, situation template *content* (only the extractor skeleton, not the 30 episodes), benchmark scale-up, P5–P9 analyzers, integrity layer implementation.

---

## 15. Anti-patterns (do NOT do these)

- ❌ Building a "full" Groovy parser. Use regex + lightweight AST library; 70% coverage is enough — drop the rest.
- ❌ Inventing new IR fields, capabilities, predicates, roles, interaction patterns, or attack patterns without updating this file first.
- ❌ Calling LLM agents from static analyzers. Different layers.
- ❌ Implementing an activity recognizer. Use oracle labels from CASAS/ARAS.
- ❌ Conflating activity with situation. Activity is a *component* of situation.
- ❌ Building a single-timeline situation schema. Per-resident timelines are non-negotiable.
- ❌ Writing constraints that enumerate situation instances. Use situation predicates.
- ❌ Trying to detect P5–P9 patterns in `cascade_builder.py`. They need their own analyzers (Week 2+) and/or the integrity layer (§4.5). Don't pre-build.
- ❌ Implementing the integrity layer (§4.5) in Week 1. Interface only; no implementation.
- ❌ Optimizing for hypothetical attacks not in §1.4 or §8.3.
- ❌ Polishing a deliverable past current-phase quality.
- ❌ Committing dataset files.
- ❌ Silently "fixing" a rule or episode that doesn't fit the IR / situation schema. Drop it and log it.

---

*Last updated: Week 1 kickoff (revision 2 — interaction pattern taxonomy expanded from P1–P5 to P1–P9; situation integrity defense layer §4.5 introduced; attack patterns AP6–AP8 added). Update this file via PR whenever §1–§10 substantively change.*