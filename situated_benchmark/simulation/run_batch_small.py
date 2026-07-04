# filename: simulation/run_batch_small.py
# Small-scale pipeline run: every incarnation x 10 seeds x 3 salience.
# Emits situations + a per-incarnation distribution summary (the variability
# evidence that the data isn't hand-authored). Run from simulation/:
#   python run_batch_small.py

import random, json, os
from collections import Counter, defaultdict
import seed_catalog as SC
import activity_coupling as AC
import situation_generator as G

SEEDS = list(range(10))
SALIENCES = ["clear", "typical", "subtle"]
OUT = os.path.join(os.path.dirname(__file__), "..", "output", "batch_small")


def recipe_from(seed_fixed, inc, seed, salience):
    rng = random.Random(seed * 131 + hash(salience) % 97)
    factory = inc["cause_factory"]
    sub = factory(random.Random(0)).sub_type
    primary, legal = AC.resolve_activity(
        cause_mode="coupled" if inc["activity_mode"] == "lock" else "decoupled",
        cause_sub_type=sub, trigger_entity=seed_fixed["trigger_entity"],
        time_of_day=inc["time_of_day"], rng=rng,
        pinned_activity=inc["pinned_activity"],
        locked_activity=inc["locked_activity"],
        scenario_presence=inc["scenario_presence"],
    )
    weather = inc["weather_locked"] if inc["weather_role"] == "causal" else \
        random.Random(seed).choice(["Sunny_Day","Cloudy_Day","Hazy_Polluted_Day","Cold_Clear_Night","Rainy_Day"])
    above = seed_fixed["trigger_above"] if seed_fixed["trigger_above"] is not None else 0
    return dict(
        primary_activity=primary, cause_factory=factory, weather=weather,
        salience=salience, time_of_day=inc["time_of_day"], noise_seed=seed,
        rule_id=seed_fixed["rule_id"], service=seed_fixed["service"],
        target=seed_fixed["target"], designed_intent=seed_fixed["designed_intent"],
        trigger_entity=seed_fixed["trigger_entity"], trigger_kind="state",
        trigger_above=above, weather_role=inc["weather_role"],
    )


def main():
    os.makedirs(OUT, exist_ok=True)
    triples = SC.all_incarnations()
    manifest, summary = [], {}
    total = 0
    for seed_id, fixed, inc in triples:
        inc_id = inc["incarnation_id"]
        acts, weathers, trigs, co_occ = Counter(), Counter(), [], 0
        for seed in SEEDS:
            for sal in SALIENCES:
                r = recipe_from(fixed, inc, seed, sal)
                sit = G.generate_situation(r, rng=random.Random(seed * 7 + 1))
                fn = f"{inc_id}_s{seed}_{sal}.json"
                with open(os.path.join(OUT, fn), "w") as f:
                    json.dump(sit, f)
                gf = sit["_ground_facts"]
                acts[gf["primary_activity"]] += 1
                weathers[gf["weather"]] += 1
                tv = sit["trigger"]["value_now"]
                if isinstance(tv, (int, float)):
                    trigs.append(tv)
                co_occ += int(gf["co_occurring"])
                manifest.append({"file": fn, "incarnation": inc_id,
                                 "gt": inc["gt"], "seed": seed, "salience": sal})
                total += 1
        summary[inc_id] = {
            "gt": inc["gt"], "n": len(SEEDS) * len(SALIENCES),
            "activity_dist": dict(acts),
            "weather_dist": dict(weathers),
            "trigger_range": [min(trigs), max(trigs)] if trigs else None,
            "co_occurring_count": co_occ,
        }
    with open(os.path.join(OUT, "_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    with open(os.path.join(OUT, "_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Generated {total} situations ({len(triples)} incarnations x "
          f"{len(SEEDS)} seeds x {len(SALIENCES)} salience)\n")
    print("Per-incarnation variability (the anti-hardcode evidence):\n")
    for inc_id, s in summary.items():
        acts = ", ".join(f"{k}:{v}" for k, v in sorted(s["activity_dist"].items(),
                                                        key=lambda x: -x[1])[:3])
        tr = s["trigger_range"]
        trs = f"{tr[0]}–{tr[1]}" if tr else "n/a(binary)"
        print(f"  {inc_id:<20} gt={s['gt']:<9} acts[{acts}] "
              f"trig[{trs}] co_occ={s['co_occurring_count']}/{s['n']}")


if __name__ == "__main__":
    main()
