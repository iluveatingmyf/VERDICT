import json
from simulator import load_wdg, forward_simulate, achieve_goal


def llm_call(prompt: str, expected_schema: dict | None = None) -> dict:
    """Stub: replace with your LLM client (Claude/OpenAI/etc).
       Returns parsed JSON."""
    raise NotImplementedError


def compress_wdg_nodes(wdg) -> str:
    """Produce a compact text listing of WDG nodes for prompt context."""
    lines = []
    for nid, n in wdg.nodes.items():
        bits = [f"id={nid}", f"class={n.get('class','?')}", f"area={n.get('area','?')}"]
        if n.get("measures"):     bits.append(f"measures={n['measures']}")
        if n.get("capabilities"): bits.append(f"caps={n['capabilities']}")
        lines.append("  " + ", ".join(bits))
    return "\n".join(lines)


def serialize_trace(steps) -> list[dict]:
    return [
        {"hop": s.hop,
         "effects": [{"target": e.target, "effect": e.effect,
                      "via_edge_type": e.via_edge_type, "via_edge_id": e.via_edge_id,
                      "note": e.note}
                     for e in s.effects]}
        for s in steps
    ]


def serialize_candidates(cands) -> list[dict]:
    return [
        {"device_id": c.device_id, "action": c.action,
         "via_capability": c.via_capability,
         "forward_trace": serialize_trace(c.forward_trace),
         "side_effects": [{"target": e.target, "effect": e.effect}
                          for e in c.side_effects]}
        for c in cands
    ]


def expand_property(property_text: str, wdg_path: str,
                    base_world_state: dict) -> dict:
    wdg = load_wdg(wdg_path)
    wdg_compact = compress_wdg_nodes(wdg)

    # ------------------------------------------------------------ Step 0
    seed = llm_call(
        prompt=PROMPT_STEP_0.format(
            property_text=property_text,
            wdg_nodes_compressed=wdg_compact,
        )
    )

    # ------------------------------------------------------------ Step 0.5
    grounding = llm_call(
        prompt=PROMPT_STEP_0_5.format(
            seed_sigma=json.dumps(seed),
            wdg_nodes_compressed=wdg_compact,
        )
    )
    seed["wdg_grounding"] = grounding["wdg_grounding"]
    seed["open_slots"].extend(grounding.get("open_slots", []))

    # ------------------------------------------------------------ Step 1
    forward_pack = llm_call(
        prompt=PROMPT_STEP_1.format(
            seed_sigma_with_grounding=json.dumps(seed),
            wdg_nodes_compressed=wdg_compact,
        )
    )
    forward_sigmas = forward_pack["forward_sigmas"]

    # ------------------------------------------------------------ Step 2 — phase 1
    reverse_pack = llm_call(
        prompt=PROMPT_STEP_2_PHASE_1.format(
            seed_sigma_with_grounding=json.dumps(seed),
            wdg_nodes_compressed=wdg_compact,
        )
    )
    # ------------------------------------------------------------ Step 2 — phase 2 (WDG runs)
    for rc in reverse_pack["reverse_candidates"]:
        ws = dict(base_world_state)
        ws.update(rc.get("world_state_overrides", {}))
        trigger = seed["wdg_grounding"]["trigger"]
        trace = forward_simulate(
            wdg,
            trigger={"node": trigger["node"], "event": trigger["event"]},
            world_state=ws,
        )
        rc["simulator_trace"] = serialize_trace(trace)
    # ------------------------------------------------------------ Step 2 — phase 3
    reverse_synth = llm_call(
        prompt=PROMPT_STEP_2_PHASE_3.format(
            seed_sigma=json.dumps(seed),
            reverse_candidates_with_traces=json.dumps(reverse_pack["reverse_candidates"]),
        )
    )
    reverse_sigmas = reverse_synth["reverse_sigmas"]

    # ------------------------------------------------------------ Step 3 — phase 1
    parallel_pack = llm_call(
        prompt=PROMPT_STEP_3_PHASE_1.format(
            seed_sigma_with_grounding=json.dumps(seed),
            wdg_nodes_compressed=wdg_compact,
        )
    )
    # ------------------------------------------------------------ Step 3 — phase 2 (WDG runs)
    target_sensor = seed["wdg_grounding"]["intent_target"]["target_sensor"]
    direction     = seed["wdg_grounding"]["intent_target"]["desired_direction"]
    if target_sensor and direction in ("INCREASE", "DECREASE"):
        cands = achieve_goal(wdg, target_sensor, direction, base_world_state)
        achieve_results = serialize_candidates(cands)
    else:
        achieve_results = []
    # ------------------------------------------------------------ Step 3 — phase 3
    parallel_synth = llm_call(
        prompt=PROMPT_STEP_3_PHASE_3.format(
            seed_sigma=json.dumps(seed),
            parallel_candidates=json.dumps(parallel_pack["parallel_candidates"]),
            achieve_results=json.dumps(achieve_results),
        )
    )
    parallel_sigmas = parallel_synth["parallel_sigmas"]

    # ------------------------------------------------------------ Step 4 & 5
    all_sigmas = [seed] + forward_sigmas + reverse_sigmas + parallel_sigmas
    open_slots = [{"sigma_id": s["sigma_id"], "slots": s.get("open_slots", [])}
                  for s in all_sigmas if s.get("open_slots")]
    user_questions = llm_call(
        prompt=PROMPT_STEP_5.format(
            all_sigmas_open_slots=json.dumps(open_slots),
        )
    )["user_questions"]

    return {
        "seed": seed,
        "forward": forward_sigmas,
        "reverse": reverse_sigmas,
        "parallel": parallel_sigmas,
        "user_questions": user_questions,
    }

wdg_path = "./wdg.json"
wdg = load_wdg(wdg_path)
wdg_compact = compress_wdg_nodes(wdg)
print(wdg_compact)