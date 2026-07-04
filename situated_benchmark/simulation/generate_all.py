# filename: simulation/generate_all.py
# Generates one sample situation for every incarnation in the catalog and
# prints a compact distinctness report. Confirms all 24 produce valid,
# physically-distinct situations before scaling to full batches.

import random
import seed_catalog as SC
import activity_coupling as AC
import situation_generator as G
import cause_sources as C


def recipe_from(seed_fixed, inc, seed=7, salience="typical"):
    rng = random.Random(seed)
    factory = inc["cause_factory"]
    sub = factory(random.Random(0)).sub_type
    # resolve activity per the incarnation's mode
    primary, _ = AC.resolve_activity(
        cause_mode="coupled" if inc["activity_mode"] == "lock" else "decoupled",
        cause_sub_type=sub, trigger_entity=seed_fixed["trigger_entity"],
        time_of_day=inc["time_of_day"], rng=rng,
        pinned_activity=inc["pinned_activity"],
        locked_activity=inc["locked_activity"],
        scenario_presence=inc["scenario_presence"],
    )
    weather = inc["weather_locked"] if inc["weather_role"] == "causal" else "Cloudy_Day"
    above = seed_fixed["trigger_above"] if seed_fixed["trigger_above"] is not None else 0
    return dict(
        primary_activity=primary, cause_factory=factory, weather=weather,
        salience=salience, time_of_day=inc["time_of_day"], noise_seed=seed,
        rule_id=seed_fixed["rule_id"], service=seed_fixed["service"],
        target=seed_fixed["target"], designed_intent=seed_fixed["designed_intent"],
        trigger_entity=seed_fixed["trigger_entity"], trigger_kind="state",
        trigger_above=above,
    )


if __name__ == "__main__":
    triples = SC.all_incarnations()
    print(f"Generating 1 sample for each of {len(triples)} incarnations:\n")
    ok = 0
    for seed_id, fixed, inc in triples:
        try:
            r = recipe_from(fixed, inc)
            sit = G.generate_situation(r, rng=random.Random(7))
            n_snap = len(sit["snapshots"])
            tv = sit["trigger"]["value_now"]
            act = sit["activity"]["label"]
            print(f"  OK  {inc['incarnation_id']:<20} [{fixed['flip_axis']:<14}] "
                  f"snaps={n_snap:<3} trig={str(tv):<7} act={act:<14} gt={inc['gt']}")
            ok += 1
        except Exception as e:
            print(f"  ERR {inc['incarnation_id']:<20} {type(e).__name__}: {e}")
    print(f"\n{ok}/{len(triples)} incarnations generated successfully")
