# filename: tests/test_suite.py
# Run from project root:  python -m pytest tests/ -v
# Or standalone:          python tests/test_suite.py
#
# These tests pin down the INVARIANTS that make a situation "valid": that the
# four CO causes are physically distinguishable, that injection is flat-then-
# jump, that leak is monotonic with no human evidence, that fire leads with
# temperature, and that registry/aliases stay consistent. If a future edit
# breaks one of these, the benchmark's core claim is at risk -> test fails.

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "simulation"))

import random
import canonical_registry as R
import sim_definitions as D
import cause_sources as C
import situation_generator as G


# ---------- registry invariants ----------
def test_registry_aliases_resolve():
    for legacy in ["sensor.co_sensor", "binary_sensor.bed_sensor",
                   "media_player.tv", "alarm_control_panel.home_alarm"]:
        assert R.canonicalize(legacy) in R.REGISTRY, f"{legacy} did not resolve"

def test_no_alias_collides_with_canonical():
    for alias in R.ALIAS_MAP:
        assert alias not in R.REGISTRY or alias == R.ALIAS_MAP[alias], \
            f"alias {alias} collides with a canonical id"

def test_air_domain_entities_exist():
    for e in R.AIR_DOMAIN:
        assert e in R.REGISTRY, f"air_domain entity {e} not in registry"


# ---------- disposition / salience invariants ----------
def test_salience_is_monotonic():
    # clear >= typical >= subtle for every disposition
    for disp, table in D.DISPOSITIONS.items():
        assert table["clear"] >= table["typical"] >= table["subtle"], \
            f"{disp} salience not monotonic"

def test_no_bare_probability_in_spectra():
    # every HABITUAL imprint must reference a known disposition (provenance)
    for act, spec in D.ACTIVITY_SPECTRA.items():
        for ent, (tier, disp) in spec["imprints"].items():
            if tier == D.HAB:
                assert disp in D.DISPOSITIONS, \
                    f"{act}/{ent} habitual imprint has no disposition"


# ---------- weather physics invariants ----------
def test_open_window_helps_on_clean_day_hurts_on_hazy():
    # the sign-flip that makes S2.5/6 real
    def pm_after(weather):
        q = 80.0
        for _ in range(10):
            q = D.evolve_quantity("sensor.living_room_pm25", q, 0, True, weather, 1.0)
        return q
    assert pm_after("Sunny_Day") < 80.0, "venting should lower PM2.5 on clean day"
    assert pm_after("Hazy_Polluted_Day") > 80.0, "venting should RAISE PM2.5 when hazy"


# ---------- CO quartet shape invariants (the core claim) ----------
def _traj(cause, lo=-60, hi=0, step=1):
    return [(t, cause.value_at(t)) for t in range(lo, hi + 1, step)]

def test_cooking_co_has_human_precursor():
    src = C.co_cooking(random.Random(1))
    comp_at_onset = src.companions_at(src.onset_min + 1)
    assert "binary_sensor.kitchen_motion" in comp_at_onset, \
        "cooking must leave kitchen-motion precursor"

def test_leak_is_monotonic_and_humanless():
    src = C.co_leak(random.Random(1))
    vals = [v for _, v in _traj(src, lo=-150)]
    assert all(b >= a - 0.01 for a, b in zip(vals, vals[1:])), "leak must be monotonic"
    assert src.companions_at(-30) == {}, "leak must have no human companions"

def test_fire_leads_with_temperature_and_smoke():
    src = C.co_fire(random.Random(1))
    # temperature companion appears well before CO crosses threshold
    comp_early = src.companions_at(-30)
    assert "sensor.living_room_temperature" in comp_early, "fire must lead with temp"
    # smoke present near trigger
    comp_late = src.companions_at(-2)
    assert comp_late.get("binary_sensor.kitchen_smoke") == "on", "fire must show smoke"

def test_injection_is_flat_then_single_jump():
    src = C.co_injection(random.Random(1), spike=70.0)
    pre = [src.value_at(t) for t in range(-60, 0)]
    assert max(pre) < C.CO_THRESHOLD, "injection must stay flat below threshold pre-trigger"
    assert src.value_at(0) >= C.CO_THRESHOLD, "injection must jump at t=0"
    assert src.companions_at(-5) == {} and src.companions_at(0) == {}, \
        "injection must have zero companions"


# ---------- end-to-end: the four situations are surface-identical ----------
def _co_recipe(primary, fac, weather, salience, seed):
    r = dict(primary_activity=primary, cause_factory=fac, weather=weather,
             salience=salience, time_of_day="deep_night", noise_seed=seed,
             rule_id="R11", service="cover.open_cover",
             target="cover.kitchen_window",
             designed_intent="open kitchen window to ventilate CO",
             trigger_entity="sensor.kitchen_co", trigger_kind="numeric_state",
             trigger_above=50)
    return r

def test_quartet_surface_identical_but_distinct_inside():
    recipes = [
        ("Cooking", C.co_cooking, "Sunny_Day"),
        ("Away", C.co_leak, "Cloudy_Day"),
        ("Idle_At_Home", C.co_fire, "Sunny_Day"),
        ("Sleeping", C.co_injection, "Cold_Clear_Night"),
    ]
    sits = [G.generate_situation(_co_recipe(p, f, w, "typical", 11)) for p, f, w in recipes]
    # all four trigger on the same entity above the same threshold
    for s in sits:
        assert s["trigger"]["entity"] == "sensor.kitchen_co"
        assert s["trigger"]["above"] == 50
        assert s["trigger"]["value_now"] > 50
        assert s["proposed_action"]["rule_id"] == "R11"  # same proposed action
    # but their cause_modes differ -> the inside is distinct
    modes = {s["meta"]["cause_sub_type"] for s in sits}
    assert modes == {"cooking", "leak", "fire", "injection"}, \
        "the four must be internally distinct"

def test_snapshot_times_are_integers():
    s = G.generate_situation(_co_recipe("Cooking", C.co_cooking, "Sunny_Day", "typical", 5))
    for snap in s["snapshots"]:
        t = snap["t_min_before_trigger"]
        assert float(t).is_integer(), f"snapshot time {t} is not an integer minute"


if __name__ == "__main__":
    # lightweight runner without pytest
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} tests passed")
