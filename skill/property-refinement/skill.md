---
name: property-refinement
description: Expand ONE natural-language smart-home property (safety, security, utility, or preference) into a finite set of intent-level specification fragments by making three domain-general moves — SCOPE, EXCEPT, GENERALIZE — on its (trigger, action, intent) skeleton. Use whenever the user gives a TAP/IFTTT-style rule, a "should/should-not" policy, or any IF-THEN property and wants its situated variants. Trigger even on a bare paste plus "process this" / "expand this" / "find the exceptions". Output is intent-level and device-independent; binding an intent to a concrete device is a separate later stage this skill does not perform. Run the staged pipeline and emit the schema — do not hand-wave a prose list.
---

# Property Refinement

Take ONE property and recover the situational dimensions it silently compresses away. The original property is kept as the system-level default. On top of it we generate **sigma** — intent-level specification fragments — by making three moves on the property's skeleton. The moves ask the same questions of every property, which is what keeps the skill general rather than tied to any domain.

This skill is offline distillation feeding human review. Its output is **NOT** auto-deployed: a person audits, edits, and confirms each sigma before it enters the runtime library. Every sigma therefore carries a `review_status` telling the reviewer where to look hardest.

## What this skill outputs

Output is at the **intent level**: a goal verb on an abstract object, not a device state. A later stage, with the home's actual device topology, decides which physical device realizes an intent; this skill does not do that and names no device. The practical test for a well-formed action: if it reads like a goal you could say aloud, it is right; if it reads like a service call, the intent has collapsed back onto a device and should be re-lifted to a goal on an abstract object.

A sigma whose correct response is to do nothing writes its `abstract_action` as `no_action`. There is no separate field for "how this differs from the default": the relation is read off by comparing `abstract_action` to the skeleton's action — same action = the default holds; `no_action` = the default is withheld; an opposite or reduced action = the default is overridden or eased. The action content already says all of this.

## Why this shape

A static property hides the dimensions that decide whether its action is right *now*: the **cause** of a reading, its **trajectory** over time, **who** is present and their state, and any overriding situation. It also hides something subtler — the property is only correct inside an **implicit scene** its author took for granted, and that scene is nowhere in the device state. A property's *action* is bound to one device, but its *intent* is not: lift the intent off the device and it can reach scenes and objects the device-level statement never could. The three moves below each exploit a different one of these hidden dimensions.

## Step 0 — Skeleton + intent lift (always first)

Extract:
- `trigger` — the IF / WHEN condition.
- `action` — the mandated THEN action; mark `must_do` or `must_not_do`.
- `intent` — the *purpose* the action serves; push past the surface. The action is a means, not the end. Ask what state of the world the action is trying to bring about or prevent, phrased without naming the device the property happens to use.
- `intent_lifted` — restate that intent with the original device removed, as a device-agnostic goal or threat. This is the pivot the moves grow from.
- `intent_confidence` — `high | low`. If the intent had to be guessed, mark low; every sigma derived under a low-confidence intent inherits `review_status: confirm_required`.

A thin intent (one that just restates the action) yields thin sigma — flag it.

Run `EXCEPT` and `GENERALIZE` against `intent_lifted`, not the narrow original trigger. This is the core mechanism that surfaces cause-driven reversals: by asking "under what specific causes or trajectories does the mandated action, executed as written, actively betray or defeat this newly lifted intent?", the model can discover severe hidden risks (e.g., feeding a secondary hazard or aggravating a systemic crisis) that are entirely invisible if you only look at the surface trigger.

## The three moves

Each move holds a different part of the skeleton fixed and varies the rest. They are not one operation under three names; keeping them distinct is what keeps them honest.

| move | holds fixed | varies | recovers which hidden dimension |
|------|-------------|--------|----------------------------------|
| SCOPE      | action + intent | the trigger's implicit conditions | the **implicit scene** the property assumed |
| EXCEPT     | trigger + intent | the action | **cause / trajectory / occupant-state / overrides** |
| GENERALIZE | intent          | trigger **and** object | the intent's reach **beyond its origin device** |

### SCOPE — make the property's implicit applicability explicit
A property as written looks unconditional, but it is only correct inside a scene its author silently assumed. SCOPE surfaces that scene — the conditions that were never written into the trigger because they were taken for granted, none of which live in the device state.
> "Under what unstated assumptions is this property actually the right thing? What scene did its author take for granted?"

Emit one full sigma object per assumption made explicit — not a passing note. Each SCOPE sigma is a first-class library entry exactly like an EXCEPT or GENERALIZE sigma: it has `move: SCOPE`, an activation stating the scene, `abstract_action` equal to the property's default action (do as written), and all other fields populated. 

The sigma's information is the boundary itself, not a different action — it is the system's **positive anchor**: it tells the runtime mediator "when the situation falls inside this scene and no EXCEPT fires, executing the default is affirmatively correct." Without these, the library has only exceptions and generalizations and no sigma asserting the original property's normal range of validity — the mediator could not distinguish "no exception fired, so the default is right" from "this situation was never considered." Always produce at least one SCOPE sigma. Everything outside the SCOPE boundary is where EXCEPT lives.

### EXCEPT — when the action betrays its (lifted) intent
> "In what situations does the mandated action, executed as written, fail the lifted intent — or harm another value?"

Ask this against `intent_lifted`, so cause-driven betrayals surface (see Step 0). For each, name the situation (`activation`), the value it protects (`primary_protect`), any values it sacrifices (`trades_off_against`), and what the action becomes (`abstract_action` — an opposite action, a reduced one, or `no_action`). 

Favor exceptions driven by **cause, trajectory, occupant state, or an overriding situation** — things unreadable from the trigger instant. These are the reason a runtime mediator beats static rewriting; surface them. (Do NOT label them "non-rewriteable" here — whether static rewriting truly fails is measured downstream against a baseline, not asserted offline.)

### GENERALIZE — grow the intent to new occasions and objects
This move changes the output type: it does not situate the original property, it mints *new* candidate sigmas serving the same lifted intent. Run it as a chain:
1. Start from `intent_lifted`.
2. **Situation axis** — what *other* occasions expose or serve this intent, beyond the original trigger?
3. **Object axis** — what *other* objects or channels realize or threaten this intent, beyond the original device?
4. Emit **one sigma per axis, at the family level** — never one per instance. A single family-level sigma covers all instances of a class; enumerating dimensions rather than the cross-product of instances is what keeps the set finite.
5. **Put the human-readable enumeration in `activation`; put a machine-comparable label in `generalized_class`.** These are two different jobs:
   * `activation` (free text, for humans + the runtime matcher) must enumerate the class's members inline, especially the **non-obvious** ones the original trigger did not mention. For a sigma generalized from "hallway at night" to "any low-light passage", write "any low-light passage a person traverses (hallway, stairwell, garage walkway, a room whose only lamp just failed — any path where footing is unclear)", not a bare "any low-light passage". The test: read the activation as an adversarial judge and ask "could I justify excluding the non-obvious member?" — if yes, the extension is under-specified; name it explicitly.
   * `generalized_class` (a closed label JSON object, NOT free text) records which class this sigma covers, so a downstream stage can compare classes mechanically. Pick one `object_class` and/or one `occasion_class` token from the closed lists below. The loose enumeration lives only in `activation`; do not repeat it here. A single short token label pair is all this field holds.

**Closed class vocabularies for `generalized_class`** (do not invent tokens; if none fits, the generalization is probably too narrow or the lists need a deliberate extension — flag it, do not coin ad hoc):
* **object_class**: `entry_path` | `illumination_source` | `air_channel` | `thermal_channel` | `surveillance_channel` | `power_channel` | `alerting_channel`
* **occasion_class**: `unguarded_period` | `low_visibility` | `occupant_present` | `out_of_band_environment` | `in_progress_activity` | `emergency_event`

The generalized object class is exactly what lets one property's intent reach another property's scene at runtime. Every GENERALIZE sigma is **speculative** — a derived spec may not match what the resident wants and carries the highest false-positive risk of the three moves — so mark it `derived: true` and `review_status: confirm_required`; it must pass the user checklist before entering any library.

## Integration is a separate stage (this skill only leaves the hook)

De-duplicating and conflict-checking sigmas across properties is **NOT** this skill's job — it takes ONE property and cannot see the others, so it has no global view and must not attempt comparison. It leaves exactly one cheap hook: every GENERALIZE sigma tags its `generalized_class` with a closed label from the fixed lists. Because the label is a token (not free text), a downstream integration stage — which does have the global view — can compare labels mechanically: two sigmas with the same `object_class` or `occasion_class` are duplicate/conflict candidates to examine. This skill only assigns the label; it performs no comparison and produces no cross-property output.

## Fixed vocabularies (use these tokens only)

**protect_target** — the value an item protects/optimizes. Priority high→low resolves conflicts. Used for BOTH `primary_protect` (exactly one) and `trades_off_against` (zero or more, must be different values from primary):
`personal_safety` > `physical_security` > `privacy` > `task_completion` > `comfort` > `energy`

* `primary_protect` is the single value the sigma exists to serve.
* `trades_off_against` records the other values the action sacrifices or touches. Do NOT split one coupled action into two same-activation sigmas — record the sacrifice here instead.
* A tension within one value (e.g. indoor safety vs. outdoor safety, both `personal_safety`) is **NOT** a trade-off against another value. Leave `trades_off_against` empty and describe the intra-value tension in `note`; never put `primary_protect`'s own value into `trades_off_against` (self-reference is invalid).

This six-level ordering is a **deliberate design commitment, not a domain-neutral primitive**. It is an ontology ordering, not rule-to-rule hard-coding. The closure buys cross-property comparability: the `personal_safety` raised by one property and by an unrelated property are the same class at the same rank, so sigmas from different properties can meet and be compared in one runtime.

**abstract_action**: a goal verb on an abstract object, never a service call. The single token `no_action` denotes doing nothing. Coin the verb from the property at hand; do not draw from a fixed list.

**temporal_scope**: `instant` (act once at the event) | `sustaining` (the condition must hold over a period; any violation during it should be corrected).

**observable** — a runtime note: could a mediator auto-detect this sigma's activation? `yes` | `partial` | `no`. `no` cannot auto-activate → at runtime it can only be surfaced as a user prompt. Name the abstract `signal_class` — `time` | `activity` | `occupancy` | `trajectory` | `cause-evidence` | `external-alarm` — never a device. Note: `observable` is a runtime attribute and is **SEPARATE** from `review_status` (the human-audit axis); do not conflate them.

**review_status** — the human-audit axis; every sigma gets exactly one:
* `confident` — well-grounded in the lifted intent and a concrete signal; reviewer can likely approve quickly.
* `exploratory` — a plausible surfaced situation that may or may not match the resident's real expectation; reviewer MUST scrutinize.
* `confirm_required` — MUST be explicitly confirmed before use, because it either (a) is `derived: true` (every GENERALIZE sigma), or (b) has `observable: no`, or (c) derives from a low confidence intent, or (d) reverses/suppresses a `personal_safety` or `physical_security` action (high blast radius if wrong).

## Output schema (emit valid JSON)

```json
{
  "property_id": "P_<short_slug>",
  "source": "<citation if given, else 'user-provided'>",
  "skeleton": {
    "trigger": "...",
    "action": "...",
    "action_modality": "must_do | must_not_do",
    "intent": "...",
    "intent_lifted": "device-agnostic goal/threat — the pivot",
    "intent_confidence": "high | low"
  },
  "sigmas": [
    {
      "sigma_id": "<prop>.<move>.<slug>",
      "move": "SCOPE | EXCEPT | GENERALIZE",
      "label": "human-readable; not used by logic",
      "activation": "situation predicate(s), described semantically — no device, no entity_id; concrete and sensor-evidence-decidable; lists extensions for GENERALIZE",
      "primary_protect": "<one of the 6>",
      "trades_off_against": ["<other protect_target values; empty if none>"],
      "temporal_scope": "instant | sustaining",
      "intent_served": "which lifted intent this sigma serves",
      "abstract_action": "goal verb on an abstract object, or `no_action`; never a service call",
      "generalized_class": {
        "object_class": "entry_path | illumination_source | air_channel | thermal_channel | surveillance_channel | power_channel | alerting_channel | null",
        "occasion_class": "unguarded_period | low_visibility | occupant_present | out_of_band_environment | in_progress_activity | emergency_event | null"
      },
      "observable": "yes | partial | no",
      "signal_class": "time | activity | occupancy | trajectory | cause-evidence | external-alarm",
      "review_status": "confident | exploratory | confirm_required",
      "derived": false,
      "note": "optional; human-facing"
    }
  ],
  "user_checklist": [
    "plain-language line per sigma ending in [Y/N]; confirm_required items first",
    "Add your own: ____"
  ]
}

```

`derived` is `true` for every GENERALIZE sigma, `false` otherwise. The system-level default (execute the original action when no sigma activates) is a global rule, not a per-property field.

## Worked examples

*Each block is a trace of running the three moves on one property — read it as output, not a template. These examples are deliberately drawn from domains unrelated to any particular test input to maintain evaluation integrity. The one deliberate domain commitment is the `protect_target` value ontology.*

### Example — `IF motion is detected in the hallway at night, the hallway light turns on`

**Step 0** — trigger: motion detected in hallway at night · action: turn the hallway light on (must_do) · intent: give a person moving in the dark enough visibility to move safely · intent_lifted: `provide_safe_passage_illumination` · intent_confidence: high.

**SCOPE** — surface the assumed scene; each becomes a full sigma carrying the default action, anchoring where the property is affirmatively correct:

* `hallway.SCOPE.movement_needs_light` — activation: "the moving entity is an occupant navigating the space who requires active visual guidance." abstract_action: `provide_safe_passage_illumination`. primary_protect=`personal_safety`, trades_off_against=[], temporal_scope=`instant`, observable=`yes`, signal_class=`activity`, review_status=`confident`, derived=false.
* `hallway.SCOPE.no_sleep_disruption` — activation: "no other occupants are sleeping in directly adjacent spaces where light leakage would cause disturbance." abstract_action: `provide_safe_passage_illumination`. primary_protect=`comfort`, trades_off_against=[], temporal_scope=`sustaining`, observable=`partial`, signal_class=`occupancy`, review_status=`confident`, derived=false.

**EXCEPT** (asked against `provide_safe_passage_illumination`, not just "turn on light"):

* override = sleeping nearby: the movement occurs during quiet hours while a nearby occupant is sleeping, meaning full illumination violates their rest → abstract_action: `provide_minimal_floor_guidance`. primary_protect=`comfort`, trades_off_against=[`task_completion`], temporal_scope=`sustaining`, observable=`partial`, signal_class=`time`, review_status=`confirm_required`.
* cause = environmental ambient: the motion coincides with evidence that the passage is already adequately illuminated by moonlight or adjacent architectural lighting → abstract_action: `no_action`. primary_protect=`energy`, trades_off_against=[], temporal_scope=`instant`, observable=`yes`, signal_class=`cause-evidence`, review_status=`confident`.

**GENERALIZE**

* situation axis: hallway-at-night → any low-visibility passage an occupant traverses.
* object axis: hallway light → any localized illumination source.
* one family-level sigma: an occupant traverses any inadequately lit architectural path → `provide_safe_passage_illumination`. activation: "any low-light passage a person traverses (hallway, stairwell, garage walkway, a room whose only lamp just failed — any path where footing is unclear)." generalized_class: { "object_class": "illumination_source", "occasion_class": "low_visibility" }. temporal_scope=`instant`, primary_protect=`personal_safety`, derived=true, review_status=`confirm_required`.

### Example — `IF indoor temperature exceeds a high threshold, turn on the air conditioner`

**Step 0** — trigger: temperature crosses a high threshold · action: turn AC on (must_do) · intent: bring an uncomfortable indoor temperature back into a tolerable range · intent_lifted: `restore_thermal_comfort_band` · intent_confidence: high.

**SCOPE** — surface the assumed scene; each becomes a full sigma carrying the default action:

* `climate.SCOPE.occupant_present` — activation: "occupants are currently inside or their imminent return vector indicates they will require a cooled space." abstract_action: `restore_thermal_comfort_band`. primary_protect=`comfort`, trades_off_against=[], temporal_scope=`sustaining`, observable=`yes`, signal_class=`max_occupancy`, review_status=`confident`, derived=false.
* `climate.SCOPE.sustained_ambient_rise` — activation: "the high reading reflects a genuine, sustained increase in ambient thermal energy throughout the zone." abstract_action: `restore_thermal_comfort_band`. primary_protect=`comfort`, trades_off_against=[], temporal_scope=`sustaining`, observable=`yes`, signal_class=`trajectory`, review_status=`confident`, derived=false.

**EXCEPT** (asked against `restore_thermal_comfort_band`):

* occupancy = empty home: the home is completely vacant with no return telemetry detected for an extended duration → abstract_action: `no_action`. primary_protect=`energy`, trades_off_against=[`comfort`], temporal_scope=`sustaining`, observable=`yes`, signal_class=`occupancy`, review_status=`exploratory`.
* trajectory = transient thermal spike: the sudden high reading is caused by a localized, transient heat spike with a known self-dissipating cause (e.g., briefly opening a hot oven door next to the sensor) rather than a room-wide rise → abstract_action: `defer_and_recheck`. primary_protect=`energy`, trades_off_against=[], temporal_scope=`instant`, observable=`partial`, signal_class=`trajectory`, review_status=`confident`.

**GENERALIZE**

* situation axis: high-temperature → any out-of-band thermal deviation (extreme heat or cold).
* object axis: air conditioner → any active environmental HVAC or climate modulation loop.
* one family-level sigma: indoor ambient conditions drift outside the standard habitable comfort envelope while occupants are present → `restore_thermal_comfort_band`. activation: "indoor temperature or thermal load leaves the safe/comfortable residential band (extreme summer heatwave, sudden winter heating failure) while occupants are exposed." generalized_class: { "object_class": "thermal_channel", "occasion_class": "out_of_band_environment" }. temporal_scope=`sustaining`, primary_protect=`comfort`, derived=true, review_status=`confirm_required`.

## Self-check before emitting

* Did Step 0 lift the intent off the device, and did EXCEPT/GENERALIZE run against the LIFTED intent (so cause-driven reversals surface)?
* Did SCOPE surface assumptions NOT in the device state (an implicit scene), rather than tuning a strength knob, and emit at least one full SCOPE sigma carrying the default action as the property's positive anchor?
* Did you run all three moves, or justify skipping one?
* Did GENERALIZE land on a different object or occasion than the original, at the family level — with the member enumeration (including the non-obvious ones) written into `activation`, and a closed `generalized_class` label assigned from the fixed lists?
* Is every `abstract_action` a goal-on-abstract-object or `no_action`, never a device call?
* Is `primary_protect` exactly one of the six, are coupled sacrifices recorded in `trades_off_against` (never self-referencing primary), and intra-value tensions in `note`?
* Is `review_status` set, with `confirm_required` for derived / observable:no / low-confidence intent / safety reversals?
* Is the user checklist jargon-free, `confirm_required` items first?

## Note on "static rewriteability" (intentionally NOT a field)

Whether a sigma could instead be captured by a static condition on the trigger is NOT decidable offline — it depends on how a concrete static baseline behaves on the sigma's situation. Asserting it here would be a guess. We therefore do not tag it. EXCEPT deliberately surfaces cause/trajectory/true-vs-reported/override exceptions; whether those genuinely defeat static rewriting is measured downstream by comparing a best-effort static baseline against the runtime mediator. That measurement, not an offline label, is the evidence that situated runtime mediation is needed.

