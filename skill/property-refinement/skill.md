---
name: property-refinement
description: Distill a single natural-language smart-home safety/correctness property into a structured set of forward refinements and reverse exceptions, each tagged with observability and a protected target, plus a user-confirmation checklist. Use this skill whenever the user provides a TAP/IFTTT-style property, a smart-home "should/should-not" rule, or any IF-THEN safety policy and wants it broken into situated variants for runtime mediation. Trigger this even when the user just pastes a property and says "process this", "refine this", "find the exceptions", or "what situations break this rule" — do not hand-wave a list in prose; run the full staged pipeline and emit the structured schema.
---

# Property Refinement

Turn ONE natural-language property into a **finite set of situated refinements**:
the original property stays as a runtime **fallback**, and we generate **forward
refinements** (when to enforce harder) and **reverse exceptions** (when the
property should be softened, reversed, or suppressed). Each item is tagged so a
downstream runtime mediator can activate it from observable signals, and so
conflicts between items resolve by a fixed priority.

This skill is **offline distillation only**. It does NOT do runtime classification
and does NOT emit Home-Assistant DSL. It produces the reusable spec library that
those later stages consume.

## Core idea (why this shape)

A static property compresses away the dimensions that actually decide whether its
action is appropriate right now (the *cause* of a sensor reading, the *trajectory*
over time, *who* is present, an overriding *safety* situation). We do not invent a
new naming scheme for situations. Instead we anchor everything to the property
itself: the property is the default, and we enumerate a bounded set of
situated corrections on top of it. The total spec space is therefore finite and
every item is traceable to one published property.

## Fixed vocabularies (do not invent new tokens outside these)

**protect_target** — what the item protects/optimizes. Exactly one per item.
Priority order (higher wins on conflict):

1. `personal_safety`   (bodily harm: fire escape, scalding, falling, medical)
2. `physical_security` (intrusion, unauthorized physical access, locks)
3. `privacy`           (surveillance, recording, data exposure)
4. `task_completion`   (an in-progress human activity that must not be broken)
5. `comfort`           (visibility, thermal comfort, convenience)
6. `energy`            (power waste, noise, unnecessary actuation)

**direction** — how the item modifies the original mandated action:

- `enforce`   keep / strengthen the original action
- `soften`    do a reduced-intensity version (pick a weaker item from action_pool)
- `reverse`   do the opposite of the original action (e.g. unlock instead of lock)
- `suppress`  do nothing (skip the action entirely)

**observable** — can a runtime mediator actually detect this item's activation?

- `yes`     a concrete signal exists (sensor/state/time/event)
- `partial` inferable but noisy (needs trajectory or multi-signal fusion)
- `no`      depends on something unsensable (mood, intent never expressed) →
            this item CANNOT auto-activate; it is demoted to "prompt user only"

## The pipeline — run all six steps, in order

### Step 1 — Parse the property skeleton
Extract three things and state them explicitly:
- `trigger`   the IF condition(s)
- `action`    the mandated THEN action (note if it's a MUST-do or MUST-NOT-do)
- `intent`    WHY the action exists — the goal it serves. Ask "what is this action
              actually protecting against / trying to achieve?" This is the hook
              that makes reverse exceptions derivable. If intent is unclear, give
              the most defensible reading and flag it.

### Step 2 — Forward refinements
With the trigger satisfied, find situations where the property should be
**enforced harder or more reliably**. These sharpen the default; usually few.
For each, fill the item schema with direction=`enforce`.
Skip this step if no meaningful strengthening exists — do not pad.

### Step 3 — Reverse exceptions (the core step)
With the trigger STILL satisfied, find situations where executing the action
would **violate the resident's real expectation**. For each exception ask:
- what situation triggers it (the `activation`, must be concrete)
- what it protects (`protect_target`, from the fixed list)
- how it modifies the action (`direction`: soften / reverse / suppress)

Push specifically for exceptions that **cannot be expressed as a static condition
on the trigger** — ones that depend on cause, trajectory, presence/identity, or an
external overriding situation. These are the items that distinguish situated
mediation from static rule-rewriting; mark each such item `static_rewriteable: no`.

Do NOT enumerate the situation space exhaustively (that is the trap). Enumerate the
*dimensions* the property is sensitive to, then give one representative exception
per dimension.

### Step 4 — Observability check
For every item from Steps 2–3, set the `observable` field and name the
`signal_source` you'd use at runtime. If `observable: no`, the item stays in the
output but is flagged as **prompt-user-only** (it cannot auto-activate). This is
also the gate that proves an item is runtime-usable at all.

### Step 5 — User confirmation checklist
Emit a short, plain-language checklist the resident can approve/reject/edit:
one line per item, no jargon. Example line:
"When there's a fire alarm, UNLOCK the doors instead of locking them — keep this? [Y/N]"
Only items the user confirms should enter the library. Always include an
"add your own exception" slot.

### Step 6 — Emit the library entry
Output the full structured object (schema below). This is the reusable artifact.

## Output schema

Emit valid JSON in this exact shape:

```json
{
  "property_id": "P_<short_slug>",
  "source": "<corpus/citation if given, else 'user-provided'>",
  "skeleton": {
    "trigger": "...",
    "action": "...",
    "action_modality": "must_do | must_not_do",
    "intent": "...",
    "intent_flagged_uncertain": false
  },
  "fallback": "execute original action (= current-system behavior) when no item activates",
  "items": [
    {
      "kind": "forward | reverse",
      "label": "human-readable, not used by logic",
      "activation": "concrete situation predicate(s)",
      "protect_target": "<one of the 6>",
      "direction": "enforce | soften | reverse | suppress",
      "action_pool": ["abstract action options, device-independent, ordered strong->weak"],
      "observable": "yes | partial | no",
      "signal_source": "what runtime signal detects this (or 'none')",
      "static_rewriteable": true,
      "note": "optional"
    }
  ],
  "user_checklist": [
    "plain-language line per item ending in [Y/N]",
    "Add your own exception: ____"
  ]
}
```

Field rules:
- `action_pool` is **device-independent abstract actions** ("path-level lighting",
  "full brightness"), NOT entity IDs. Local device mapping happens later.
- `static_rewriteable: false` means a static condition bolted onto the trigger
  cannot capture this item — these are your differentiators; surface them.
- Keep one `protect_target` per item. If an item seems to serve two, split it.

## Worked example (use as the few-shot pattern)

**Input property:** `IF nobody_home THEN lock all doors`  (source: common security SmartApp)

**Step 1 — skeleton:**
- trigger: occupancy = nobody_home
- action: lock all doors (must_do)
- intent: prevent unauthorized physical entry while the home is unoccupied

**Step 2 — forward refinement:**
- When nobody_home AND a prior intrusion/tamper event occurred recently → enforce
  harder (lock + arm alarm). protect_target=physical_security, observable=yes
  (alarm/contact-sensor history), static_rewriteable=yes.

**Step 3 — reverse exceptions:**
- Fire alarm active → people may be evacuating; locking can trap them.
  direction=reverse (unlock egress), protect_target=personal_safety.
  Depends on an EXTERNAL safety situation unrelated to occupancy →
  static_rewriteable=NO (you can't express "fire overrides everything" as a
  condition on the occupancy trigger cleanly). observable=yes (smoke/heat alarm).
- Occupancy sensor reports nobody_home but a person is still inside (sensor blind
  spot / multi-occupant household where one member is undetected) → locking +
  arming may trap or falsely alarm. direction=suppress, protect_target=personal_safety.
  Depends on TRUE presence vs REPORTED presence → static_rewriteable=NO,
  observable=partial (needs multi-signal presence fusion / trajectory).
- Medical emergency / inbound EMS expected → doors should be reachable.
  direction=reverse, protect_target=personal_safety, observable=partial
  (depends on an explicit emergency signal), static_rewriteable=no.

**Step 4 — observability:** fire=yes; presence-blindspot=partial; EMS=partial.

**Step 5 — checklist (plain language):**
- "If there's a fire alarm, UNLOCK the doors instead of locking — keep this? [Y/N]"
- "If the system thinks nobody's home but someone is actually inside, DON'T lock/arm — keep this? [Y/N]"
- "During a medical emergency, keep doors reachable — keep this? [Y/N]"
- "Add your own exception: ____"

**Step 6:** emit the JSON object per schema above.

Note how every reverse exception here is anchored to the *intent* (prevent
unauthorized entry) and how the strongest ones (fire, presence blind-spot) are
`static_rewriteable: no` — those are exactly the cases a static trigger-condition
patch cannot handle and a runtime situated mediator can.

## Quality bar (self-check before emitting)
- Did you give the property's `intent`, not just restate the action?
- Does every item have a concrete `activation` and a `signal_source`?
- Did you produce at least one `static_rewriteable: false` exception (if the
  property plausibly has one)? If not, say why none exists.
- Is every `protect_target` from the fixed 6-item list?
- Is `action_pool` device-independent?
- Is the user checklist free of jargon?
- You enumerated DIMENSIONS, not an exhaustive situation list?
