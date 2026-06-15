"""
WDG Simulator: Function A (forward) and Function B (goal-directed backward + forward).

Design notes
------------
- Sensor nodes act as both physical-variable proxies and event sources (per user decision).
- CAUSAL edges carry a top-level `polarity` field. Three values are recognized:
    "+"           -> source ON pushes target value up
    "-"           -> source ON pushes target value down
    "conditional" -> direction depends on `condition_expr` evaluated against world_state
    "inhibit"     -> source disables target's ability to execute actions (power gating)
    "conditional_on_mode" -> direction depends on the source's own state value (e.g. HVAC mode)
- Function A: BFS over LOGICAL + CAUSAL edges; outputs hop-numbered Steps. No wall clock.
- Function B: capability filter -> instance enumeration -> forward simulate each candidate.
  Output is a list of Candidates, each with a device.action() call and a forward trace.

Reviewer-relevant choices
-------------------------
- We DO NOT model time delays. Hop number == causal depth from the trigger.
- We DO NOT model sensor spoofing here; world_state is trusted (threat model aligns with
  HAWatcher's "trust the IoT platform" assumption).
- Physical channel taxonomy (illuminance/temperature/humidity/air_quality/...) reused from
  HAWatcher [Fu et al., USENIX Security 2021] Section 5.3.2.
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

EffectSign = str  # "INCREASE" | "DECREASE" | "STABILIZE" | "INHIBITED" | "ON" | "OFF" | "FIRED"


@dataclass
class Effect:
    """A single change attributed to a hop."""
    target: str
    effect: EffectSign
    via_edge_type: str       # "LOGICAL" | "CAUSAL"
    via_edge_id: str         # rule_id for LOGICAL, "<src>-><tgt>" for CAUSAL
    note: str = ""


@dataclass
class Step:
    """One BFS hop. All effects in a step are treated as concurrent."""
    hop: int
    effects: list[Effect] = field(default_factory=list)


@dataclass
class Candidate:
    """A device-level action proposed by Function B."""
    device_id: str
    action: str                       # e.g. "fan.turn_on", "cover.open_cover"
    via_capability: str               # which capability matched
    forward_trace: list[Step] = field(default_factory=list)
    side_effects: list[Effect] = field(default_factory=list)  # effects on variables other than the target


# ---------------------------------------------------------------------------
# WDG container
# ---------------------------------------------------------------------------

class WDG:
    def __init__(self, raw: dict):
        self.raw = raw
        self.nodes: dict[str, dict] = {n["id"]: n for n in raw["nodes"]}
        self.edges: list[dict] = raw["edges"]
        # Pre-index for fast traversal.
        self._out_logical: dict[str, list[dict]] = {}
        self._out_causal:  dict[str, list[dict]] = {}
        self._in_causal:   dict[str, list[dict]] = {}
        for e in self.edges:
            srcs = e["source"] if isinstance(e["source"], list) else [e["source"]]
            tgts = e["target"] if isinstance(e["target"], list) else [e["target"]]
            for s in srcs:
                if e["type"] == "LOGICAL":
                    self._out_logical.setdefault(s, []).append(e)
                else:
                    self._out_causal.setdefault(s, []).append(e)
            for t in tgts:
                if e["type"] == "CAUSAL":
                    self._in_causal.setdefault(t, []).append(e)

    def out_logical(self, node_id: str) -> list[dict]:
        return self._out_logical.get(node_id, [])

    def out_causal(self, node_id: str) -> list[dict]:
        return self._out_causal.get(node_id, [])

    def in_causal(self, node_id: str) -> list[dict]:
        return self._in_causal.get(node_id, [])

    def node(self, node_id: str) -> Optional[dict]:
        return self.nodes.get(node_id)

    def all_devices(self) -> list[dict]:
        return [n for n in self.nodes.values()
                if "capabilities" in n]

    def all_sensors(self) -> list[dict]:
        return [n for n in self.nodes.values()
                if n.get("class") == "sensor"]


# ---------------------------------------------------------------------------
# Condition expression evaluator
# ---------------------------------------------------------------------------
# Minimal grammar:  <var> <op> <var_or_literal>
#   var ::= node_id (looked up in world_state)
#   op  ::= > | < | >= | <= | == | !=
# Used only for CONTEXTUAL_EFFECT edges. No AND/OR yet; not needed by current WDG.

_OP = {
    ">":  lambda a, b: a >  b,
    "<":  lambda a, b: a <  b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}
_EXPR_RE = re.compile(r"^\s*([\w\.]+)\s*(>=|<=|==|!=|>|<)\s*([\w\.]+|-?\d+(?:\.\d+)?)\s*$")


def evaluate_condition(expr: str, world_state: dict[str, Any]) -> bool:
    m = _EXPR_RE.match(expr)
    if not m:
        raise ValueError(f"unsupported condition expression: {expr!r}")
    lhs, op, rhs = m.group(1), m.group(2), m.group(3)
    lhs_val = _resolve(lhs, world_state)
    rhs_val = _resolve(rhs, world_state)
    return _OP[op](lhs_val, rhs_val)


def _resolve(token: str, world_state: dict[str, Any]) -> Any:
    # numeric literal
    try:
        return float(token)
    except ValueError:
        pass
    # node id
    if token in world_state:
        return world_state[token]
    raise KeyError(f"condition references unknown variable: {token}")


# ---------------------------------------------------------------------------
# Edge effect resolution
# ---------------------------------------------------------------------------

def _resolve_causal_effect(edge: dict,
                           source_state: Any,
                           world_state: dict) -> Optional[EffectSign]:
    """Given a CAUSAL edge and the current source state, return the effect sign,
    or None if the edge does not fire under this state."""
    props = edge["properties"]
    ctype = props.get("causal_type")

    if ctype == "INHIBITING_EFFECT":
        for em in props["effect_map"]:
            if em["if_source_state"] == source_state:
                return em["then_target_actions"]   # "INHIBITED"
        return None

    if ctype == "DIRECT_IMPACT":
        for em in props["effect_map"]:
            if em["if_source_state"] == source_state:
                return em["then_effect"]
        return None

    if ctype == "CONTEXTUAL_EFFECT":
        # effect direction depends on condition_expr
        cond = evaluate_condition(props["condition_expr"], world_state)
        branch = props["if_true_effect"] if cond else props["if_false_effect"]
        if branch["if_source_state"] == source_state:
            return branch["then_effect"]
        return None

    return None


# ---------------------------------------------------------------------------
# LOGICAL rule firing
# ---------------------------------------------------------------------------

def _logical_rule_fires(edge: dict, source_event: dict, world_state: dict) -> bool:
    """Decide whether a LOGICAL edge fires given a source event and current world state."""
    props = edge["properties"]
    trig = props["trigger"]

    # Basic trigger matching.
    if trig.get("platform") == "state":
        if source_event.get("kind") != "state":
            return False
        if "to" in trig and source_event.get("to") != trig["to"]:
            return False
        if "from" in trig and source_event.get("from") != trig.get("from"):
            return False
    elif trig.get("platform") == "numeric_state":
        if source_event.get("kind") != "numeric":
            return False
        val = source_event.get("value")
        if val is None:
            return False
        if "above" in trig and not (val > trig["above"]):
            return False
        if "below" in trig and not (val < trig["below"]):
            return False
    elif trig.get("platform") == "time":
        if source_event.get("kind") != "time":
            return False
    # else: unknown trigger type -> conservatively fire if the rule was named explicitly

    # Conditions
    conds = props.get("condition")
    if conds:
        if not _eval_ha_conditions(conds, world_state):
            return False
    return True


def _eval_ha_conditions(conds, world_state) -> bool:
    """Very small evaluator for the HA-style condition list used in our WDG."""
    if isinstance(conds, dict):
        conds = [conds]
    for c in conds:
        if "condition" in c and c["condition"] == "or":
            if not any(_eval_ha_conditions([sub], world_state) for sub in c["conditions"]):
                return False
            continue
        if "entity_id" in c and "state" in c:
            actual = world_state.get(c["entity_id"])
            expected = c["state"]
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            else:
                if actual != expected:
                    return False
        elif "condition" in c and c["condition"] == "numeric_state":
            actual = world_state.get(c["entity_id"])
            if actual is None:
                return False
            if "above" in c and not (actual > c["above"]):
                return False
            if "below" in c and not (actual < c["below"]):
                return False
    return True


# ---------------------------------------------------------------------------
# Function A: forward_simulate
# ---------------------------------------------------------------------------

# How a service call maps to the resulting source state for CAUSAL propagation.
_SERVICE_TO_STATE = {
    "fan.turn_on":          "on",
    "fan.turn_off":         "off",
    "light.turn_on":        "on",
    "light.turn_off":       "off",
    "switch.turn_on":       "on",
    "switch.turn_off":      "off",
    "cover.open_cover":     "open",
    "cover.close_cover":    "closed",
    "lock.lock":            "locked",
    "lock.unlock":          "unlocked",
    "camera.turn_on":       "on",
    "vacuum.start":         "running",
    "climate.turn_off":     "off",
    "alarm_control_panel.arm_away":     "armed_away",
    "alarm_control_panel.arm_night":    "armed_night",
    "alarm_control_panel.disarm":       "disarmed",
    "alarm_control_panel.alarm_trigger":"triggered",
}


def forward_simulate(wdg: WDG,
                     trigger: dict,
                     world_state: dict,
                     max_hops: int = 8) -> list[Step]:
    """
    trigger format:
        {"node": <id>, "event": {"kind": "state"|"numeric"|"time"|"action",
                                 "to": ...|"value": ...|"action": ...}}
    Returns a hop-ordered list of Step.
    """
    ws = dict(world_state)               # mutable copy
    steps: list[Step] = []
    # BFS frontier: list of (node_id, event_dict)
    frontier: list[tuple[str, dict]] = [(trigger["node"], trigger["event"])]
    visited_edges: set[str] = set()      # rule_id or causal signature, prevents cycles

    hop = 0
    while frontier and hop < max_hops:
        next_frontier: list[tuple[str, dict]] = []
        step = Step(hop=hop)

        for node_id, event in frontier:
            # 1) Fire LOGICAL rules whose trigger matches.
            for edge in wdg.out_logical(node_id):
                rid = edge["properties"].get("rule_id", f"L:{node_id}")
                if rid in visited_edges:
                    continue
                if not _logical_rule_fires(edge, event, ws):
                    continue
                visited_edges.add(rid)
                action = edge["properties"]["action"]
                service = action["service"]
                targets = edge["target"] if isinstance(edge["target"], list) else [edge["target"]]
                for tgt in targets:
                    # Check inhibition before applying.
                    if _is_inhibited(wdg, tgt, ws):
                        step.effects.append(Effect(
                            target=tgt, effect="INHIBITED",
                            via_edge_type="LOGICAL", via_edge_id=rid,
                            note=f"action {service} blocked by power gating"))
                        continue
                    new_state = _SERVICE_TO_STATE.get(service, "fired")
                    ws[tgt] = new_state
                    step.effects.append(Effect(
                        target=tgt,
                        effect=f"STATE={new_state}",
                        via_edge_type="LOGICAL", via_edge_id=rid))
                    # Schedule downstream: this target may now be a source of further rules
                    # and of CAUSAL physical effects.
                    next_frontier.append((tgt, {"kind": "state", "to": new_state}))

            # 2) Propagate CAUSAL effects driven by the current source state.
            source_state = ws.get(node_id)
            if source_state is None:
                continue
            for edge in wdg.out_causal(node_id):
                csig = f"C:{node_id}->{edge['target']}@{source_state}"
                if csig in visited_edges:
                    continue
                eff = _resolve_causal_effect(edge, source_state, ws)
                if eff is None:
                    continue
                visited_edges.add(csig)
                tgt = edge["target"]
                step.effects.append(Effect(
                    target=tgt,
                    effect=eff,
                    via_edge_type="CAUSAL",
                    via_edge_id=csig,
                    note=f"channel={edge['properties'].get('channel','?')}"))
                # We do not push physical variable changes back into frontier as triggers
                # by default. They become triggers only if a LOGICAL rule subscribes to
                # the corresponding numeric threshold; that linkage is captured implicitly
                # when the rule re-fires on the next hop based on ws.
                # To enable that, we update ws with a coarse direction marker:
                if eff in ("INCREASE", "DECREASE"):
                    ws.setdefault(f"{tgt}::trend", eff)

        if step.effects:
            steps.append(step)
        frontier = next_frontier
        hop += 1

    return steps


def _is_inhibited(wdg: WDG, device_id: str, world_state: dict) -> bool:
    for edge in wdg.in_causal(device_id):
        props = edge["properties"]
        if props.get("causal_type") != "INHIBITING_EFFECT":
            continue
        src = edge["source"]
        src_state = world_state.get(src)
        for em in props["effect_map"]:
            if em["if_source_state"] == src_state and em["then_target_actions"] == "INHIBITED":
                return True
    return False


# ---------------------------------------------------------------------------
# Function B: achieve_goal
# ---------------------------------------------------------------------------

# Map (capability, desired_direction) -> candidate (device-class, action).
# Direction conventions: "DECREASE", "INCREASE".
# For "conditional" edges, the caller must inspect world_state separately;
# we still propose the candidate and let the forward simulation reveal the actual sign.
_CAPABILITY_ACTIONS = {
    "air_purification":      [("fan", "turn_on", "DECREASE", "pm25/aqi")],
    "humidity_reduction":    [("fan", "turn_on", "DECREASE", "humidity")],
    "co_reduction":          [("switch", "turn_on", "DECREASE", "co")],
    "co2_reduction":         [("fan", "turn_on", "DECREASE", "co2")],
    "ventilation":           [("fan", "turn_on", "DECREASE", "air_quality_generic"),
                              ("cover", "open_cover", "CONDITIONAL", "air_quality_generic")],
    "outdoor_air_exchange":  [("cover", "open_cover", "CONDITIONAL", "temperature_or_aqi")],
    "thermal_exchange":      [("cover", "open_cover", "CONDITIONAL", "temperature")],
    "heating":               [("climate", "set_hvac_mode_heat", "INCREASE", "temperature")],
    "cooling":               [("climate", "set_hvac_mode_cool", "DECREASE", "temperature")],
    "illumination":          [("light", "turn_on",  "INCREASE", "illuminance"),
                              ("light", "turn_off", "DECREASE", "illuminance")],
}


def achieve_goal(wdg: WDG,
                 target_sensor: str,
                 desired_direction: str,        # "INCREASE" | "DECREASE"
                 world_state: dict,
                 max_candidates: int = 20) -> list[Candidate]:
    """
    Backward search:
        1) For every CAUSAL edge that points to target_sensor and whose effect under
           current world_state matches desired_direction, collect the source device.
        2) Plus: find devices whose capability claims to move this channel in that
           direction (capability registry).
        3) For each candidate device, propose its action and run forward_simulate to
           obtain the full physical impact, including side effects on other variables.
    """
    target_node = wdg.node(target_sensor)
    if target_node is None or target_node.get("class") != "sensor":
        raise ValueError(f"{target_sensor} is not a sensor node")
    target_channel = target_node.get("measures")

    candidates: list[Candidate] = []
    seen: set[tuple[str, str]] = set()  # dedup on (device, action)

    # ---- (1) edge-driven discovery: walk in_causal(target_sensor) ----
    for edge in wdg.in_causal(target_sensor):
        if not edge["properties"].get("reversible", False):
            continue
        src = edge["source"]
        src_node = wdg.node(src)
        if src_node is None:
            continue
        # Probe each plausible source state.
        for source_state, action in _enumerate_device_actions(src_node):
            ws_probe = dict(world_state)
            ws_probe[src] = source_state
            eff = _resolve_causal_effect(edge, source_state, ws_probe)
            if eff == desired_direction:
                key = (src, action)
                if key in seen:
                    continue
                seen.add(key)
                cand = _build_candidate(wdg, src, action, world_state,
                                        target_sensor, via_cap="(direct-edge)")
                candidates.append(cand)

    # ---- (2) capability-driven discovery ----
    for cap, options in _CAPABILITY_ACTIONS.items():
        for cls_prefix, action_name, direction_label, channel_tag in options:
            if direction_label != desired_direction and direction_label != "CONDITIONAL":
                continue
            # Find devices providing this capability that plausibly affect this channel.
            for dev in wdg.all_devices():
                if cap not in dev.get("capabilities", []):
                    continue
                if not dev["id"].startswith(cls_prefix + "."):
                    continue
                # Channel-relevance gate: does this device have any in_causal edge to a
                # sensor whose `measures` matches target_channel?
                if not _device_can_affect_channel(wdg, dev["id"], target_channel):
                    continue
                action = _action_str(dev["class"], action_name)
                key = (dev["id"], action)
                if key in seen:
                    continue
                seen.add(key)
                cand = _build_candidate(wdg, dev["id"], action, world_state,
                                        target_sensor, via_cap=cap)
                candidates.append(cand)

    # Filter: only keep candidates whose forward trace actually moves the target
    # in the desired direction (this rejects CONDITIONAL ones that go the wrong way
    # under current world_state).
    confirmed: list[Candidate] = []
    for c in candidates:
        if _trace_moves_target(c.forward_trace, target_sensor, desired_direction):
            # Compute side effects: everything in trace that is not the target sensor.
            c.side_effects = [
                ef for step in c.forward_trace for ef in step.effects
                if ef.target != target_sensor and ef.effect in ("INCREASE", "DECREASE")
            ]
            confirmed.append(c)
        if len(confirmed) >= max_candidates:
            break
    return confirmed


# Helpers for Function B

def _enumerate_device_actions(dev: dict) -> list[tuple[str, str]]:
    """Return plausible (resulting_state, action_call) pairs for a device."""
    cls = dev.get("class")
    table = {
        "fan":     [("on",  f"{dev['id']}.turn_on"),  ("off", f"{dev['id']}.turn_off")],
        "light":   [("on",  f"{dev['id']}.turn_on"),  ("off", f"{dev['id']}.turn_off")],
        "switch":  [("on",  f"{dev['id']}.turn_on"),  ("off", f"{dev['id']}.turn_off")],
        "cover":   [("open",f"{dev['id']}.open_cover"),("closed",f"{dev['id']}.close_cover")],
        "climate": [("heat",f"{dev['id']}.set_hvac_mode(heat)"),
                    ("cool",f"{dev['id']}.set_hvac_mode(cool)"),
                    ("off", f"{dev['id']}.turn_off")],
    }
    return table.get(cls, [])


def _action_str(cls: str, action_name: str) -> str:
    return f"{cls}.{action_name}"


def _device_can_affect_channel(wdg: WDG, device_id: str, channel: Optional[str]) -> bool:
    if channel is None:
        return True
    for edge in wdg.out_causal(device_id):
        tgt = wdg.node(edge["target"])
        if tgt and tgt.get("measures") == channel:
            return True
        edge_channel = edge["properties"].get("channel")
        # Loose match: pm25/aqi/co/co2 all map to channel="air_quality"
        if edge_channel == "air_quality" and channel and channel.startswith("air_quality"):
            return True
    return False


def _build_candidate(wdg: WDG, device_id: str, action: str,
                     world_state: dict, target_sensor: str,
                     via_cap: str) -> Candidate:
    # Construct the trigger event for forward simulation.
    new_state = _action_to_state(action)
    ws = dict(world_state)
    ws[device_id] = new_state
    trace = forward_simulate(
        wdg,
        trigger={"node": device_id, "event": {"kind": "state", "to": new_state}},
        world_state=ws,
    )
    # Also inject a hop-0 step describing the action itself, so the trace reads naturally.
    head = Step(hop=0, effects=[Effect(
        target=device_id, effect=f"STATE={new_state}",
        via_edge_type="ACTION", via_edge_id=action)])
    full_trace = [head] + [Step(hop=s.hop + 1, effects=s.effects) for s in trace]

    return Candidate(
        device_id=device_id,
        action=action,
        via_capability=via_cap,
        forward_trace=full_trace,
    )


def _action_to_state(action: str) -> str:
    # action is like "fan.air_purifier.turn_on" or "cover.x.open_cover"
    if action.endswith(".turn_on"):     return "on"
    if action.endswith(".turn_off"):    return "off"
    if action.endswith(".open_cover"):  return "open"
    if action.endswith(".close_cover"): return "closed"
    if "set_hvac_mode(heat)" in action: return "heat"
    if "set_hvac_mode(cool)" in action: return "cool"
    return "fired"


def _trace_moves_target(trace: list[Step], target: str, desired: str) -> bool:
    for step in trace:
        for ef in step.effects:
            if ef.target == target and ef.effect == desired:
                return True
    return False


# ---------------------------------------------------------------------------
# Pretty printer for traces (for inspection / paper figures)
# ---------------------------------------------------------------------------

def format_trace(steps: list[Step]) -> str:
    out = []
    for s in steps:
        out.append(f"  Step {s.hop}:")
        for ef in s.effects:
            note = f"  ({ef.note})" if ef.note else ""
            out.append(f"    [{ef.via_edge_type:7s} {ef.via_edge_id}] "
                       f"{ef.target} -> {ef.effect}{note}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Entrypoint convenience
# ---------------------------------------------------------------------------

def load_wdg(path: str = "wdg.json") -> WDG:
    with open(path) as f:
        return WDG(json.load(f))


if __name__ == "__main__":
    wdg = load_wdg()
    print(f"Loaded WDG: {len(wdg.nodes)} nodes, {len(wdg.edges)} edges.")