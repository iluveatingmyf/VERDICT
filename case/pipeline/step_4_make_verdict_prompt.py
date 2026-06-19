# -*- coding: utf-8 -*-
"""第4步【代码】：把 激活结果+WDG事实+优先级+DSL 拼成裁决prompt。
用法: python step4_make_verdict_prompt.py <sid>
注意: DSL_SPEC 目前是占位(4+2 primitive)。你给我完整DSL后，只改 DSL_SPEC 这一段。"""
import json, sys, os

# ==================== 完整 VERDICT Plan DSL（用户提供）====================
DSL_SPEC = """The output plan MUST be written in the VERDICT Plan DSL.

DESIGN PRINCIPLES (obey all three):
1. Minimal primitive set. 2. Compositional (primitives may nest, e.g. DELAY(5m) DENY(action)).
3. Symbolically validatable — every plan must be statically checkable, so conditions
   must be fully sensor/state-grounded (no vague predicates).

PRIMITIVES:
- EXECUTE:  service.call(entity_id, {params})      -> execute the service call now
- DENY:     DENY(action)                           -> permanently block this action for this trigger instance
- ADAPT:    ADAPT(action with {new_params})        -> execute the action with modified params
- AFTER:    AFTER(condition) action                -> execute action once condition holds
- DELAY:    DELAY(duration) action                 -> execute action after a fixed delay
- PARALLEL: [action_1; action_2; ...]              -> run actions concurrently
- SEQUENCE: action_1 -> action_2                   -> run in order (next only after previous completes)
- notify.silent(target, msg) / notify.audible(target, msg)

CONDITION grammar for AFTER (STRICTLY limited — do NOT invent vague conditions):
  condition ::= entity_state_predicate | duration_elapsed | conjunction(c1, c2)
  entity_state_predicate ::= entity_id operator value      operator ::= == | != | < | > | <= | >=
  duration_elapsed ::= duration_since(entity_id, state, duration)
  duration ::= integer ('s'|'m'|'h'|'d')   e.g. 30s, 5m, 2h, 1d
  ALLOWED:  AFTER(binary_sensor.living_room_motion == 'off')
            AFTER(duration_since(binary_sensor.living_room_motion, 'off', '5m'))
            AFTER(conjunction(sensor.temperature > 20, sensor.smoke == 'off'))
  FORBIDDEN: AFTER(activity_change), AFTER(user_intent_shifted)  -- too vague, not sensor-grounded

EXAMPLE PLANS (illustrative SYNTAX patterns only — the entity_ids below are
abstract placeholders and do NOT correspond to any real case; never copy them):
  Pass-through (allow):  []        # no violation -> no intervention; winning_requirement = null
  Single reject:        [DENY(lock.unlock(door_a))]
  Param override:       [ADAPT(fan.fan_a.turn_on({for: '15m'}))]
  Cascade mediation:    [ fan.fan_a.turn_on(),
                          DENY(light.light_a.turn_off),
                          AFTER(binary_sensor.motion_a == 'off') DELAY(5m) light.light_a.turn_off() ]
  Spoof + silent alert: [ DENY(cover.cover_a.open), notify.silent(phone_a, 'sensor anomaly') ]
  Parallel emergency:   [ DENY(cover.cover_b.open), lock.unlock(door_a), lock.unlock(door_b),
                          alarm_control_panel.alarm_trigger(hazard_x), notify.audible(occupants_a, EMERGENCY) ]
Note: these five span allow / reject / adapt / cascade / emergency — do NOT infer that
intervention is the default; many cases are pass-through. Pick the verdict the facts warrant.

Write dsl_plan as a list of strings forming ONE valid plan in this DSL.
"""

PRIORITY=["personal_safety","physical_security","privacy","task_completion","comfort","energy"]

SYS_VERDICT = """You are the MEDIATION & VERDICT stage of a smart-home property mediator.
The activation stage already decided which situated requirements (sigmas) are ACTIVE
and whether the proposed_action violates each. A symbolic WDG simulator already computed
the proposed_action's real consequences and a set of candidate ALTERNATIVE actions with
their side effects. You do NOT recompute physics; you reason over the given facts.

INPUTS:
1. PROPOSED_ACTION: the automation's default action now firing.
2. ACTIVE_REQUIREMENTS: the active sigmas, each with protect_target and whether the
   proposed_action violates it, plus each sigma's stated reason.
3. PRIORITY (fixed, NON-NEGOTIABLE): personal_safety > physical_security > privacy >
   task_completion > comfort > energy. A lower-priority requirement may NEVER override
   a higher one.
4. WDG_FACTS: proposed_action's consequence chain, and candidate alternative actions
   with side effects (symbolically computed, trustworthy).
5. DSL: the plan language you must output the decision in.

DO:
- Resolve conflicts: if the proposed_action violates any active requirement, the
  highest-priority violated requirement decides. Among equal priority, prefer the
  requirement whose activation is more specific AND whose stated rationale still holds
  (e.g. if a SCOPE requirement that the default action depends on was judged inactive,
  the rationale resting on it no longer holds and cannot justify the action).
- Choose MINIMAL intervention serving the winning requirement:
  pass-through < ease < replace < deny/escalate. Never intervene harder than the
  winning protect_target warrants.
- If you DENY but a legitimate active need remains (e.g. a real hazard requirement),
  pick an ALTERNATIVE from WDG_FACTS that serves it WITHOUT violating the winning
  requirement; prefer fewer/no side effects.
- TWO-SIDED-RISK PRINCIPLE (important): when the default action is the means to satisfy
  one active safety need BUT that same action violates another active safety/security
  need, do NOT simply deny and do nothing — doing nothing may abandon a hazard that
  could be real, while doing the default may inflict the other harm. Seek an action that
  hedges BOTH risks: prefer a REPLACE that still serves the threatened need through a
  channel which does NOT incur the violated need's harm, AND raise the appropriate
  notification so a human can adjudicate the residual uncertainty. Reserve a bare DENY
  for when no hedging action exists. (You judge what the hedge and the notification are
  from the facts; this is a reasoning principle, not a fixed recipe.)
- Note: an active requirement may rest on a reading whose cause is uncorroborated. This
  does NOT let you dismiss it (the hazard might be real) NOR blindly serve it (it might
  be spurious); it is exactly the case the two-sided-risk principle is for.
- INTERACT_USER is a LAST RESORT, never a default or a way to avoid deciding. Use it ONLY when BOTH hold: (a) you have ALREADY placed a safe hedging action in `dsl_plan` that runs NOW and keeps the home safe REGARDLESS of the user's answer (the user's reply only refines the follow-up, it is not what makes the home safe); AND (b) the residual uncertainty is something the system cannot resolve from available signals in principle (it needs a human's real-time/in-person judgement). If a verdict can be derived from PRIORITY + facts, you MUST decide it yourself — do NOT offload it to the user. The interaction_prompt's A/B options are follow-up refinements layered on top of the already-safe hedge, not a substitute for it.
- Express the final decision as a DSL plan.
- Then DISTILL a REUSABLE CONSTRAINT: the general rule this case implies, phrased as
  "WHEN <situation> FORBID/REQUIRE <action-class>". State it at the semantic level
  (a later code step will expand it to concrete device states via the WDG).

OUTPUT JSON ONLY:
{
  "winning_requirement": "<sigma_id or null if pass-through>",
  "winning_protect_target": "...",
  "verdict": "ALLOW | DENY | REPLACE | INTERACT_USER",
  "chosen_alternative": "<action from WDG_FACTS, or null>",
  "dsl_plan": ["...DSL lines... — for INTERACT_USER this is the SAFE HEDGE that runs NOW, independent of the user's answer"],
  "rationale": "...",
  "interaction_prompt": {
    "_when_to_use": "ONLY when verdict==INTERACT_USER",
    "question": "concise question to the human",
    "options": [
      {"id":"A","text":"...","resulting_plan":["...DSL..."]},
      {"id":"B","text":"...","resulting_plan":["...DSL..."]}
    ]
  },
  "reusable_constraint": {
    "reusable": true,
    "reuse_basis": "WHY this is (or is not) safe to freeze into a permanent policy. Only mark reusable=true when: (1) it is driven by a STANDING REQUIREMENT (a maintain-while-situation rule), not a one-off event/fault; (2) its trigger features are STABLE, observable situation classes (occupancy/time/presence), not a specific numeric value or one-time snapshot; (3) it does NOT depend on an uncorroborated reading being true. If any fails, set reusable=false and say which.",
    "when_situation": "the STABLE situational precondition that should gate this policy (the winning standing-requirement's scene, e.g. an occupancy/time class) — NOT the full current snapshot",
    "forbid_or_require": "FORBID | REQUIRE",
    "action_class": "semantic action class in your own words (e.g. opening any access channel)",
    "target_device_class": ["<pick ONE OR MORE from the FIXED list below — this is what a later pure-lookup step expands to concrete devices; do NOT invent tokens>"],
    "protect_target": "...",
    "reason": "..."
  }
}

FIXED target_device_class tokens (choose the ones the action_class acts on; these map
to device capabilities, NOT to specific entities):
- "access_channel"        : doors / windows / garage / gate — anything that opens a path INTO the dwelling (covers + locks)
- "powered_ventilation"   : fans / range hood / whole-house fan — moves/exhausts air WITHOUT opening the envelope
- "outdoor_air_exchange"  : windows / vents opened for outside air (overlaps access_channel when it is a window)
- "air_purification"      : purifiers / scrubbers that clean air in place
- "illumination"          : lights
- "thermal"               : heater / AC / climate
- "alarming"              : sirens / alarm panel / audible+visual alerts
- "access_control"        : locks specifically (the locking mechanism)
- "power_gating"          : main power / supply cutoffs
- "surveillance"          : cameras
Use the token whose capability the action_class is really acting on. E.g. "activate
non-entry ventilation" -> ["powered_ventilation"] (NOT access_channel); "keep every
entry path secured" -> ["access_channel"]; "sound an evacuation alert" -> ["alarming"].
Note on the reusable_constraint: it is what a later code step freezes into a pure
device-state policy for lookup WITHOUT calling an LLM again. So lock ONLY the stable
features that determine this verdict (the winning standing-requirement's situational
precondition), never the incidental current snapshot. If this verdict is a one-off
hedge against an uncorroborated reading, set reusable=false — a temporary cautious
response must not become a permanent rule."""

sid=sys.argv[1]
base=f"./case/cacase/{sid}"
act=json.load(open(f"{base}/02_activation_result.json"))
facts=json.load(open(f"{base}/03_wdg_facts.json"))
lib={s["sigma_id"]:s for s in json.load(open("../properties/confirmed_properties.json"))["sigmas"]}

# 给每条 active σ 补上 protect_target / reason，组成“评审意见”
active=[]
for a in act.get("activations",[]):
    if a.get("verdict")=="active":
        s=lib.get(a["sigma_id"],{})
        active.append({"sigma_id":a["sigma_id"],
            "protect_target":s.get("protect_target","?"),
            "violated_by_proposed_action":a.get("violated_by_proposed_action",False),
            "reason":a.get("reason","")})

payload={
  "PROPOSED_ACTION": facts["proposed_action"],
  "ACTIVE_REQUIREMENTS": active,
  "PRIORITY": PRIORITY,
  "WDG_FACTS": {"delta_of_proposed_action":facts["delta_of_proposed_action"],
                "alternatives":facts["alternatives_for_trigger_goal"]},
}
prompt = SYS_VERDICT + "\n\n===== DSL =====\n" + DSL_SPEC + \
    "\n\n===== CASE =====\n" + json.dumps(payload,indent=2,ensure_ascii=False) + \
    "\n\nNow output the verdict JSON only."
open(f"{base}/04_verdict_prompt.txt","w").write(prompt)
print(f"[OK] {base}/04_verdict_prompt.txt  ({len(prompt)} chars)")
print(f"  active需求 {len(active)} 条 | 候选替代 {len(facts['alternatives_for_trigger_goal'])} 个")