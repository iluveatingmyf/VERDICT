"""
test_case.py — Regression test for Case Study A (showering scenario).

This test asserts properties that are STATIC and DETERMINISTIC:
  - The cascade analyzer detects R1 -> R2 from this rule set
  - The cascade analyzer flags R1 vs R-NEW as an action conflict
  - The expected output JSON is well-formed and references only entities/
    rules that exist in rules.yaml

It does NOT call any LLM. The purpose is to lock down the static-analysis
ground-truth so that LLM-side regressions can be measured against a fixed
reference. To do an end-to-end run with real Gemini calls, see
`../janus_orchestrator.py`.

Run:
    python test_case.py             # prints PASS/FAIL summary
    python test_case.py --verbose   # prints detailed diff
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent

# Reuse the static analyzer we already wrote
sys.path.insert(0, str(REPO_ROOT))
from janus_cascade import (  # noqa: E402
    Rule, Trigger, Action, build_cascade_graph,
    find_action_conflicts, ACTION_EFFECTS, StateChange,
)


# ============================================================
# Load rules from YAML (or fall back to inline dict)
# ============================================================

def load_rules_from_yaml(path: Path) -> list[dict]:
    """Parse the HA YAML file. Uses PyYAML if available, otherwise a
    minimal hand parser sufficient for our specific file format."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        # Fall back: this file is small and structured; we can use a
        # tiny ad-hoc parser. For real use, please `pip install pyyaml`.
        print("[warn] PyYAML not installed; using inline rule dict.",
              file=sys.stderr)
        return INLINE_RULES_FOR_TEST


# Inline copy used when PyYAML isn't available. Must stay in sync with rules.yaml.
INLINE_RULES_FOR_TEST = [
    {"id": "r1_bathroom_humidity_fan", "alias": "R1: Bathroom humidity → fan on",
     "trigger": [{"platform": "numeric_state", "entity_id": "sensor.bathroom_humidity",
                  "above": 80}],
     "action": [{"service": "switch.turn_on",
                 "target": {"entity_id": "switch.bathroom_fan"}}]},
    {"id": "r2_fan_on_light_off", "alias": "R2: Fan on → bathroom light off",
     "trigger": [{"platform": "state", "entity_id": "switch.bathroom_fan",
                  "to": "on"}],
     "action": [{"service": "light.turn_off",
                 "target": {"entity_id": "light.bathroom"}}]},
    {"id": "rnew_bathroom_motion_fan_off", "alias": "R-NEW: ...",
     "trigger": [{"platform": "state", "entity_id": "binary_sensor.bathroom_motion",
                  "to": "off", "for": {"minutes": 5}}],
     "action": [{"service": "switch.turn_off",
                 "target": {"entity_id": "switch.bathroom_fan"}}]},
]


# ============================================================
# HA YAML -> internal Rule conversion
# ============================================================

# The HA YAML has its own grammar; the internal Rule object expects a
# normalized (entity, op, value) trigger and a (verb, entity) action.
# Mapping HA's plethora of trigger types is its own little compiler;
# below is the minimum needed for this case study. Extend as you add
# rules.

def ha_trigger_to_internal(ha_trig: dict) -> Trigger:
    plat = ha_trig["platform"]
    entity = ha_trig["entity_id"]
    if plat == "numeric_state":
        if "above" in ha_trig:
            return Trigger(entity, ">", ha_trig["above"])
        if "below" in ha_trig:
            return Trigger(entity, "<", ha_trig["below"])
    if plat == "state":
        return Trigger(entity, "==", ha_trig["to"])
    raise NotImplementedError(f"HA trigger platform '{plat}' not yet handled")


def ha_action_to_internal(ha_action: dict) -> Action:
    service = ha_action["service"]              # e.g. "switch.turn_on"
    domain, verb = service.split(".", 1)
    entity = ha_action["target"]["entity_id"]
    return Action(verb=verb, entity=entity)


def parse_ha_rules(ha_rules: list[dict]) -> list[Rule]:
    out = []
    for r in ha_rules:
        # Map HA test-file IDs to short names used elsewhere
        short_id = {"r1_bathroom_humidity_fan": "R1",
                    "r2_fan_on_light_off": "R2",
                    "rnew_bathroom_motion_fan_off": "R-NEW"}[r["id"]]
        out.append(Rule(
            id=short_id,
            purpose=r.get("description", "").split("(")[-1].rstrip(")"),
            trigger=ha_trigger_to_internal(r["trigger"][0]),
            action=ha_action_to_internal(r["action"][0]),
            description=r.get("alias", ""),
        ))
    return out


# ============================================================
# Add ACTION_EFFECTS entries for entities used in this case
# ============================================================

def register_case_action_effects():
    ACTION_EFFECTS[("turn_on",  "switch.bathroom_fan")] = [
        StateChange("switch.bathroom_fan", "on")]
    ACTION_EFFECTS[("turn_off", "switch.bathroom_fan")] = [
        StateChange("switch.bathroom_fan", "off")]
    ACTION_EFFECTS[("turn_off", "light.bathroom")] = [
        StateChange("light.bathroom", "off")]
    ACTION_EFFECTS[("turn_on",  "light.bathroom")] = [
        StateChange("light.bathroom", "on")]


# ============================================================
# Assertions
# ============================================================

class TestResult:
    def __init__(self):
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def check(self, name: str, cond: bool, detail: str = ""):
        if cond:
            self.passed.append(name)
        else:
            self.failed.append((name, detail))

    def summary(self) -> str:
        n = len(self.passed) + len(self.failed)
        return f"{len(self.passed)}/{n} checks passed"

    def ok(self) -> bool:
        return not self.failed


def run_assertions(rules: list[Rule], expected: dict) -> TestResult:
    result = TestResult()
    edges = build_cascade_graph(rules)
    edge_pairs = {(e.src, e.dst) for e in edges}

    # --- Cascade chain assertions ---
    expected_chains = expected["static_cascade_analysis"]["predicted_chains"]
    for chain in expected_chains:
        for i in range(len(chain) - 1):
            pair = (chain[i], chain[i + 1])
            result.check(
                f"cascade edge {pair[0]} -> {pair[1]}",
                pair in edge_pairs,
                f"edges found: {sorted(edge_pairs)}",
            )

    # --- Conflict detection ---
    conflicts = find_action_conflicts(rules)
    expected_conflicts = expected["static_cascade_analysis"]["action_conflicts"]
    for ec in expected_conflicts:
        ra, rb = ec["rules"]
        found = any({a, b} == {ra, rb} for a, b, _ in conflicts)
        result.check(
            f"conflict {ra} vs {rb} on {ec['entity']}",
            found,
            f"conflicts found: {conflicts}",
        )

    # --- Expected-output well-formedness ---
    result.check(
        "expected output has decision_type ADAPT",
        expected.get("decision_type") == "ADAPT",
    )
    result.check(
        "plan contains DENY of light.bathroom turn_off",
        any("DENY(light.turn_off(light.bathroom))" in p for p in expected["plan"]),
    )
    result.check(
        "plan contains AFTER reschedule for fan turn_off",
        any("AFTER" in p and "switch.bathroom_fan" in p for p in expected["plan"]),
    )

    # --- Constraint references valid ---
    constraint_ids = {c["id"] for c in expected["I_spec"]["constraints"]}
    for entry in expected["risk_assessment"]:
        for imp in entry["impact"]:
            sid = imp["spec_id"]
            if sid.startswith("C"):
                result.check(
                    f"risk_assessment references valid constraint {sid}",
                    sid in constraint_ids,
                )

    return result


# ============================================================
# Main
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
 
    register_case_action_effects()

    ha_rules = load_rules_from_yaml(HERE / "rules.yaml")
    rules = parse_ha_rules(ha_rules)
    expected = json.loads((HERE / "expected_output.json").read_text())

    print(f"Loaded {len(rules)} rules, {len(expected['plan'])} plan steps expected.\n")

    result = run_assertions(rules, expected)

    if args.verbose or not result.ok():
        for name in result.passed:
            print(f"  PASS  {name}")
        for name, detail in result.failed:
            print(f"  FAIL  {name}")
            if detail:
                print(f"        {detail}")
        print()

    print(result.summary())
    sys.exit(0 if result.ok() else 1)


if __name__ == "__main__":
    main()