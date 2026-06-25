---
name: property-refinement
description: Expand ONE natural-language smart-home property (safety, security, utility, or preference) into a finite set of intent-level specification fragments by making three domain-general moves — SCOPE, EXCEPT, GENERALIZE — on its (trigger, action, intent) skeleton. Use whenever the user gives a TAP/IFTTT-style rule, a "should/should-not" policy, or any IF-THEN property and wants its situated variants. Trigger even on a bare paste plus "process this" / "expand this" / "find the exceptions". Output is intent-level and device-independent; binding an intent to a concrete device is a separate later stage this skill does not perform. Run the staged pipeline and emit the schema — do not hand-wave a prose list.
---

# Property Refinement

Take ONE property and recover the situational dimensions it silently compresses
away. The original property is kept as the runtime **fallback**. On top of it we
generate **sigma** — intent-level specification fragments — by making three moves on
the property's skeleton. The moves ask the same questions of every property, which
is what keeps the skill general rather than tied to any domain.

## What this skill outputs

Output is at the **intent level**: a goal verb on an abstract object, not a device
state. A later stage, with the home's actual device topology, decides which physical
device realizes an intent; this skill does not do that and names no device. The
practical test for a well-formed action: if it reads like a goal you could say aloud,
it is right; if it reads like a service call, the intent has collapsed back onto a
device and should be re-lifted to a goal on an abstract object.

A sigma whose correct response is to do nothing writes its `abstract_action` as
`no_action`. There is no separate field for "how this differs from the default": the
relation is read off by comparing `abstract_action` to the skeleton's action — same
action = the default holds; `no_action` = the default is withheld; an opposite or
reduced action = the default is overridden or eased. The action content already says
all of this.

## Why this shape

A static property hides the dimensions that decide whether its action is right
*now*: the **cause** of a reading, its **trajectory** over time, **who** is present
and their state, and any overriding situation. It also hides something subtler — the
property is only correct inside an **implicit scene** its author took for granted,
and that scene is nowhere in the device state. A property's *action* is bound to one
device, but its *intent* is not: lift the intent off the device and it can reach
scenes and objects the device-level statement never could. The three moves below
each exploit a different one of these hidden dimensions.

## Step 0 — Skeleton + intent lift (always first)

Extract:
- `trigger` — the IF / WHEN condition.
- `action` — the mandated THEN action; mark `must_do` or `must_not_do`.
- `intent` — the *purpose* the action serves; push past the surface. The action is
  a means, not the end. Ask what state of the world the action is trying to bring
  about or prevent, phrased without naming the device the property happens to use.
- `intent_lifted` — restate that intent with the original device removed, as a
  device-agnostic goal or threat. This is the pivot the moves grow from.

A thin intent (one that just restates the action) yields thin sigma — flag it.

## The three moves

Each move holds a different part of the skeleton fixed and varies the rest. They are
not one operation under three names; keeping them distinct is what keeps them honest.

| move | holds fixed | varies | recovers which hidden dimension |
|------|-------------|--------|----------------------------------|
| SCOPE      | action + intent | the trigger's implicit conditions | the **implicit scene** the property assumed |
| EXCEPT     | trigger         | the action | **cause / trajectory / occupant-state / overrides** |
| GENERALIZE | intent          | trigger **and** object | the intent's reach **beyond its origin device** |

### SCOPE — make the property's implicit applicability explicit
A property as written looks unconditional, but it is only correct inside a scene its
author silently assumed. SCOPE surfaces that scene — the conditions that were never
written into the trigger because they were taken for granted, none of which live in
the device state.
> "Under what unstated assumptions is this property actually the right thing? What
> scene did its author take for granted?"

Emit one sigma per assumption made explicit: its `activation` states the scene, and
its `abstract_action` is the property's default action (do as written). The sigma's
information is the boundary itself, not a different action — it marks where the
default validly holds. Everything outside that boundary is where EXCEPT lives.

### EXCEPT — when the action betrays its own intent
> "Inside or outside that scene, in what situations does the mandated action,
> executed as written, violate its own intent — or a higher-priority intent?"

For each, name the situation (`activation`), what it protects (`protect_target`),
and what the action becomes (`abstract_action` — an opposite action, a reduced one,
or `no_action`). Favor exceptions driven by **cause, trajectory, occupant state, or
an overriding situation** — things unreadable from the trigger instant — and mark
those `static_rewriteable: false`: a static condition bolted onto the trigger cannot
capture them. They are the reason a runtime mediator beats static rewriting; surface
them.

### GENERALIZE — grow the intent to new occasions and objects
This move changes the output type: it does not situate the original property, it
mints *new* candidate properties serving the same lifted intent. Run it as a chain:
1. Start from `intent_lifted`.
2. **Situation axis** — what *other* occasions expose or serve this intent, beyond
   the original trigger?
3. **Object axis** — what *other* objects or channels realize or threaten this
   intent, beyond the original device?
4. Emit **one sigma per axis, at the family level** — never one per instance. A
   single family-level sigma covers all instances of a class; enumerating dimensions
   rather than the cross-product of instances is what keeps the set finite.
5. **Spell out the family's extension in the `activation` text.** A family-level
   sigma names a *class* (e.g. "any low-light passage", "any means of illumination").
   That class name is not self-evident to a downstream judge — it must be told what
   the class includes, or it will fall back to a narrow common-sense reading and miss
   the very cases the generalization was meant to capture. So whenever the activation
   rests on a generalized class, enumerate that class's members inline, especially the
   **non-obvious** ones the original trigger did not mention. For a sigma generalized
   from "hallway at night" to "any low-light passage", write "any low-light passage a
   person traverses (hallway, **stairwell, garage walkway, a room whose only lamp just
   failed** — any path where footing is unclear)", not a bare "any low-light passage".
   The test: read the activation as an adversarial judge and ask "could I justify
   excluding the non-obvious member?" — if yes, the extension is under-specified; name
   it explicitly. This is what makes the lift actually reach beyond the origin device
   at runtime, instead of collapsing back to the one case the trigger named.

Every GENERALIZE sigma is `static_rewriteable: false` by construction. It is also
**speculative** — a derived spec may not match what the resident wants and carries
the highest false-positive risk of the three moves — so mark it `derived: true` and
require it to pass the user checklist before it enters any library.

## Fixed vocabularies (use these tokens only)

**protect_target** — exactly one per sigma; priority high→low resolves conflicts; if
a sigma serves two, split it.
`personal_safety` > `physical_security` > `privacy` > `task_completion` > `comfort` > `energy`

This six-level ordering is a **deliberate design commitment, not a domain-neutral
primitive**. Unlike `abstract_action` (open vocabulary, coined per property), this
vocabulary is **closed on purpose**: it is a small value *ontology* for the
occupied-dwelling setting, and it is what makes conflict resolution work. Two points
on why this is a feature, not a hidden hard-coding:
- It is an **ontology ordering, not rule-to-rule hard-coding.** The skill never writes
  "if sigma X conflicts with sigma Y, X wins." It assigns each sigma to a value *class*,
  and conflicts are resolved by the *class* ordering. One class (e.g. `personal_safety`)
  subsumes unboundedly many situations — a fire, a fall, a person trapped, any future
  life-threatening case maps to it automatically. Finite classes covering infinite
  instances is exactly the job of an ontology; the winner is *derived* from the
  ordering, not enumerated per situation.
- The closure buys **cross-property comparability and reproducible mediation**: the
  `personal_safety` raised by one property and by an unrelated property are the *same*
  class at the *same* rank, so sigmas from different properties can meet and be compared
  in one runtime, and any two conflicting sigmas have a determinate outcome. An open
  value vocabulary would forfeit both.
A different setting (e.g. agriculture, industrial) would supply its *own* value ontology
and ordering; the *machinery* (assign-to-class, resolve-by-class-order) is domain-neutral,
the *particular ontology* here is a stated commitment to the dwelling domain.

**abstract_action**: a goal verb on an abstract object, never a service call. The
single token `no_action` denotes the correct response being to do nothing. Coin the
verb from the property at hand; do not draw from a fixed list.

**temporal_scope**: `instant` (act once at the event) | `sustaining` (the condition
must hold over a period; any violation during it should be corrected).

**observable**: `yes` | `partial` | `no`. `no` cannot auto-activate at runtime →
demote to prompt-user-only. Name the abstract `signal_class` — time / activity /
occupancy / trajectory / cause-evidence / external-alarm — never a device. (These are
the common classes for an occupied dwelling; a different setting may extend the list —
they are signal *categories*, carrying no per-situation rule.)

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
    "intent_lifted": "device-agnostic goal/threat — the pivot"
  },
  "fallback": "execute original action (current-system behavior) when no sigma activates",
  "sigmas": [
    {
      "sigma_id": "<prop>.<move>.<slug>",
      "move": "SCOPE | EXCEPT | GENERALIZE",
      "label": "human-readable; not used by logic",
      "activation": "situation predicate(s), described semantically — no device",
      "protect_target": "<one of the 6>",
      "temporal_scope": "instant | sustaining",
      "intent_served": "which lifted intent this sigma serves",
      "abstract_action": "goal verb on an abstract object, or `no_action`; never a service call",
      "observable": "yes | partial | no",
      "signal_class": "time | activity | occupancy | trajectory | cause-evidence | external-alarm",
      "static_rewriteable": true,
      "derived": false,
      "note": "optional"
    }
  ],
  "user_checklist": [
    "plain-language line per sigma ending in [Y/N]",
    "Add your own: ____"
  ]
}
```

`derived` is `true` for every GENERALIZE sigma, `false` otherwise.

## Worked examples

*Each block is a trace of running the three moves on one property — read it as
output, not as a template. The reusable part is the questions asked, not the
specific devices. These examples are deliberately drawn from domains unrelated to
any particular test input. To be precise about the skill's domain-neutrality: the
move machinery and the action vocabulary are domain-neutral and hard-code no
situation-specific rules; the one deliberate domain commitment is the `protect_target`
value ontology (see its note above), which is a stated choice, not a hidden one.*

### Example — `IF motion is detected in the hallway at night, the hallway light turns on`

**Step 0** — trigger: motion detected in hallway at night · action: turn the
hallway light on (must_do) · intent: give a person moving in the dark enough
visibility to move safely · intent_lifted: `provide_safe_passage_illumination`
(the ceiling light is one means).

**SCOPE** — assumptions taken for granted:
- it assumes the moving person benefits from light (is awake, is navigating);
- it assumes bright light here disturbs no one else.
Each becomes an explicit-scene sigma whose `abstract_action` is the default
(`provide_safe_passage_illumination`, do as written), marking where it validly holds.

**EXCEPT**
- the motion is at an hour when another occupant is sleeping nearby and full
  brightness would wake them → `abstract_action: provide_minimal_floor_guidance`
  (a reduced action). protect=task_completion, static_rewriteable=false (depends on
  who else is present and their state, not on the motion trigger).
- the "motion" coincides with evidence the area is already adequately lit → 
  `abstract_action: no_action`. protect=energy, static_rewriteable=true.

**GENERALIZE**
- situation axis: hallway-at-night → any low-light passage a person traverses.
- object axis: ceiling light → any means of raising local illumination.
- one family-level sigma: a person traverses an inadequately lit path → 
  `provide_safe_passage_illumination` by the appropriate means.
  temporal_scope=instant, protect=personal_safety, static_rewriteable=false,
  derived=true.

### Example — `IF indoor temperature exceeds a high threshold, turn on the air conditioner`

**Step 0** — trigger: temperature crosses a high threshold · action: turn AC on
(must_do) · intent: bring an uncomfortable/unsafe indoor temperature back into a
tolerable range · intent_lifted: `restore_thermal_comfort_band`.

**SCOPE** — it assumes someone is present to benefit, and that active cooling is the
appropriate means. Each becomes an explicit-scene sigma carrying the default action,
marking where it validly holds.

**EXCEPT**
- the home is empty and no return is imminent → cooling serves no one.
  `abstract_action: no_action` (or a far weaker setpoint). protect=energy,
  static_rewriteable=false (depends on occupancy/return trajectory).
- the high reading is a transient spike with a known passing cause rather than a
  sustained rise → `abstract_action: defer_and_recheck`. protect=energy,
  static_rewriteable=false (depends on trajectory shape).

**GENERALIZE**
- situation axis: high-temperature → any out-of-band thermal condition (also too
  cold). object axis: AC → any means that moves temperature toward the band.
- one family-level sigma: indoor temperature leaves the comfort band while occupants
  are present → `restore_thermal_comfort_band` by the appropriate means.
  temporal_scope=sustaining, protect=comfort, static_rewriteable=false, derived=true.

## Self-check before emitting
- Did Step 0 lift the intent off the device?
- Did SCOPE surface assumptions that are NOT in the device state (an implicit scene),
  rather than tuning a strength knob?
- Did you run all three moves, or justify skipping one?
- Did GENERALIZE land on a different object or occasion than the original, at the
  family level — not instance by instance?
- For each GENERALIZE sigma, does its `activation` ENUMERATE the generalized class's
  members inline (including the non-obvious ones), rather than leaving a bare abstract
  class name a judge could read narrowly?
- Is every `abstract_action` a goal-on-abstract-object or `no_action`, never a device
  call?
- Is at least one EXCEPT or GENERALIZE sigma `static_rewriteable: false` (or did you
  say why none exists)?
- Is every `protect_target` one of the six, and is every `derived` sigma in the
  checklist?