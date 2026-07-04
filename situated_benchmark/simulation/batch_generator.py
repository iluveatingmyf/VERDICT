# filename: simulation/batch_generator.py
# ----------------------------------------------------------------------
# LAYER 6 (part 3): BATCH GENERATOR
#
# Ties the three sub-tasks together:
#   (1) cause->activity coupling  (activity_coupling.resolve_activity)
#   (2) extended cause sources    (cause_sources.ALL_SOURCES)
#   (3) seed x salience batching  (this file)
#
# A CASE SPEC is a compact description of one benchmark scenario. The batch
# generator expands each spec across seeds and salience levels, sampling a
# legal co-occurring activity per seed (so a leak meets DIFFERENT user
# activities across the batch), and emits a manifest.
#
# What's fixed (reproducible): the seed list and salience set.
# What varies (distribution): per-seed activity, onsets, habitual imprints,
#                             quantity values, sampled secondary.
# ----------------------------------------------------------------------

import random, json, os
import cause_sources as C
import activity_coupling as AC
import situation_generator as G


# A CaseSpec. `weather_role` decides locked vs randomized weather (criterion B
# applied to weather). `pinned_activity` set only when the case semantically
# fixes the activity (else activity is resolved freely/locked by cause).
def case_spec(case_id, trigger_entity, source_key, rule_id, service, target,
              intent, trigger_above, time_of_day, flip_axis,
              cause_mode, weather_role, weather_locked=None,
              pinned_activity=None, locked_activity=None,
              scenario_presence=None):
    return dict(
        case_id=case_id, trigger_entity=trigger_entity, source_key=source_key,
        rule_id=rule_id, service=service, target=target, intent=intent,
        trigger_above=trigger_above, time_of_day=time_of_day, flip_axis=flip_axis,
        cause_mode=cause_mode, weather_role=weather_role,
        weather_locked=weather_locked, pinned_activity=pinned_activity,
        locked_activity=locked_activity, scenario_presence=scenario_presence or {},
    )


ALL_WEATHER = ["Sunny_Day", "Cloudy_Day", "Hazy_Polluted_Day",
               "Cold_Clear_Night", "Rainy_Day"]


def _pick_weather(spec, rng):
    if spec["weather_role"] == "causal":
        return spec["weather_locked"]           # locked: weather is a causal var
    return rng.choice(ALL_WEATHER)              # nuisance: randomized for robustness


def expand_case(spec, seeds, saliences):
    """Generate all instances of one case across seeds x saliences."""
    instances = []
    factory = C.ALL_SOURCES[spec["trigger_entity"]][spec["source_key"]]
    sub_type = factory(random.Random(0)).sub_type   # peek sub_type
    for seed in seeds:
        for sal in saliences:
            rng = random.Random(seed * 1000 + hash(sal) % 1000)
            # (1) resolve the co-occurring activity legally
            primary, legal = AC.resolve_activity(
                spec["cause_mode"], sub_type, spec["trigger_entity"],
                spec["time_of_day"], rng,
                pinned_activity=spec["pinned_activity"],
                locked_activity=spec["locked_activity"],
                scenario_presence=spec["scenario_presence"],
            )
            weather = _pick_weather(spec, rng)
            recipe = dict(
                primary_activity=primary, cause_factory=factory,
                weather=weather, salience=sal, time_of_day=spec["time_of_day"],
                noise_seed=seed, rule_id=spec["rule_id"], service=spec["service"],
                target=spec["target"], designed_intent=spec["intent"],
                trigger_entity=spec["trigger_entity"], trigger_kind="numeric_state",
                trigger_above=spec["trigger_above"],
            )
            sit = G.generate_situation(recipe, rng=random.Random(seed * 7 + 1))
            sit["meta"]["case_id"] = spec["case_id"]
            sit["meta"]["flip_axis"] = spec["flip_axis"]
            sit["meta"]["weather_role"] = spec["weather_role"]
            sit["meta"]["legal_activity_set"] = legal
            instances.append(sit)
    return instances


def run_batch(specs, seeds, saliences, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    for spec in specs:
        insts = expand_case(spec, seeds, saliences)
        for i, sit in enumerate(insts):
            fname = f"{spec['case_id']}__s{sit['meta'].get('case_id','')}_{i:03d}.json"
            fname = f"{spec['case_id']}_{i:03d}.json"
            with open(os.path.join(out_dir, fname), "w") as f:
                json.dump(sit, f, indent=2)
            manifest.append({
                "file": fname, "case_id": spec["case_id"],
                "flip_axis": spec["flip_axis"], "cause_mode": sit["meta"]["cause_mode"],
                "cause_sub_type": sit["meta"]["cause_sub_type"],
                "primary_activity": sit["meta"]["primary_activity"],
                "secondary_activity": sit["meta"]["secondary_activity"],
                "weather": sit["meta"]["weather"], "salience": sit["meta"]["salience"],
                "trigger_value_now": sit["trigger"]["value_now"],
            })
    with open(os.path.join(out_dir, "_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


# ---- a few example specs (subset of the 23; full mapping is the next step) ----
EXAMPLE_SPECS = [
    case_spec("S2_1_injection", "sensor.kitchen_co", "spurious_injection",
              "R11", "cover.open_cover", "cover.kitchen_window",
              "open kitchen window to ventilate CO", 50, "deep_night",
              flip_axis="cause_mode", cause_mode="spurious",
              weather_role="nuisance", pinned_activity="Sleeping"),
    case_spec("S2_3_leak", "sensor.kitchen_co", "decoupled_leak",
              "R11", "cover.open_cover", "cover.kitchen_window",
              "open kitchen window to ventilate CO", 50, "deep_night",
              flip_axis="cause_mode", cause_mode="decoupled",
              weather_role="nuisance"),   # activity FREE -> varies per seed
    case_spec("S2_4_cooking", "sensor.kitchen_co", "coupled_cooking",
              "R11", "cover.open_cover", "cover.kitchen_window",
              "open kitchen window to ventilate CO", 50, "evening",
              flip_axis="cause_mode", cause_mode="coupled",
              weather_role="nuisance", locked_activity="Cooking"),
]


if __name__ == "__main__":
    seeds = list(range(8))
    saliences = ["clear", "typical", "subtle"]
    out = os.path.join(os.path.dirname(__file__), "..", "output", "batch")
    manifest = run_batch(EXAMPLE_SPECS, seeds, saliences, out)
    print(f"Generated {len(manifest)} instances "
          f"({len(EXAMPLE_SPECS)} cases x {len(seeds)} seeds x {len(saliences)} salience)\n")
    # show the variety: leak case meeting different activities
    print("S2_3_leak — activity varies across seeds (your concern, solved):")
    leak = [m for m in manifest if m["case_id"] == "S2_3_leak"]
    from collections import Counter
    acts = Counter(m["primary_activity"] for m in leak)
    for a, n in acts.most_common():
        print(f"    {a:<24} {n} instances")
    print(f"\n  CO_now spread (leak): "
          f"{min(m['trigger_value_now'] for m in leak)}–"
          f"{max(m['trigger_value_now'] for m in leak)}")
    print("\nInjection (pinned Sleeping) — activity stays fixed, weather varies:")
    inj = [m for m in manifest if m["case_id"] == "S2_1_injection"]
    print(f"    activities: {set(m['primary_activity'] for m in inj)}")
    print(f"    weathers:   {sorted(set(m['weather'] for m in inj))}")
