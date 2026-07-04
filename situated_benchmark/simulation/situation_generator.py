# filename: simulation/situation_generator.py
# ----------------------------------------------------------------------
# LAYER 5: SITUATION GENERATOR (core engine)
#
# Assembles a full situation JSON from a RECIPE:
#   - primary activity (+ sampled secondary via co-occurrence)  -> background imprints
#   - cause source (CO quartet etc.)                            -> foreground trigger qty
#   - weather                                                   -> physics coupling
#   - salience                                                  -> habitual-imprint p
#   - noise_seed                                                -> all randomness
#
# Sampling = fixed low-frequency grid + forced snapshots at causal events
# (activity onset, quantity crossing threshold, discontinuities), so the
# causal chain is always legible in the trajectory.
# ----------------------------------------------------------------------

import random
import json
from canonical_registry import REGISTRY, AIR_DOMAIN, canonicalize
import sim_definitions as D
import cause_sources as C


# Build the device_schema (column order) once, deterministically.
DEVICE_SCHEMA = sorted(REGISTRY.keys())
IDX = {e: i for i, e in enumerate(DEVICE_SCHEMA)}


def _default_state(entity_id):
    """Resting value for an entity when nothing sets it."""
    meta = REGISTRY[entity_id]
    t = meta["type"]
    if t == "numeric":
        return meta.get("baseline", 0.0)
    if t in ("binary", "binary_timer"):
        return "off"
    if t == "open_closed":
        return "closed"
    if t == "lock_state":
        return "locked"
    if t == "home_state":
        return "home"
    if t == "on_off_select":
        return "off"
    if t == "location_select":
        return "home"
    if t == "alarm_state":
        return "disarmed"
    if t == "media_state":
        return "off"
    if t == "hvac_mode":
        return "off"
    if t == "vacuum_state":
        return "docked"
    return "unknown"


def _apply_activity_imprints(states, activity, salience, rng):
    """Stamp a single activity's imprints into the state vector (at a time
    where the activity is active). Returns set of entities touched."""
    spec = D.ACTIVITY_SPECTRA[activity]
    touched = set()
    # presence
    for ent, val in spec["presence"].items():
        if ent in IDX:
            states[IDX[ent]] = val
            touched.add(ent)
    # imprints by tier
    for ent, (tier, disp) in spec["imprints"].items():
        ent_c = canonicalize(ent)
        if ent_c not in IDX:
            continue
        if tier == D.DET:
            states[IDX[ent_c]] = "on"
            touched.add(ent_c)
        elif tier == D.HAB:
            p = D.imprint_probability(disp, salience)
            if rng.random() < p:
                states[IDX[ent_c]] = "on"
                touched.add(ent_c)
        elif tier == D.INC:
            if rng.random() < 0.15:        # incidental = weak noise
                states[IDX[ent_c]] = "on"
                touched.add(ent_c)
    return touched


def _forced_times(cause, window_min):
    """Snapshot times that MUST be sampled so causality is legible."""
    forced = {0, round(cause.onset_min)}
    # scan for the trigger quantity crossing its threshold
    thr = C.CO_THRESHOLD if cause.quantity == "sensor.kitchen_co" else None
    if thr is not None:
        prev = cause.value_at(-window_min)
        t = -window_min
        while t <= 0:
            cur = cause.value_at(t)
            if prev < thr <= cur:
                forced.add(round(t))
            prev = cur
            t += 1
    return {f for f in forced if -window_min <= f <= 0}


def _apply_sensor_noise(states, trigger_q, companions, rng, noise_log):
    """Small drift on numeric sensors that aren't the trigger quantity and
    aren't cause companions — so readings look real, not clean integers."""
    NOISE = {
        "sensor.living_room_temperature": 0.4,
        "sensor.bathroom_humidity": 1.2,
        "sensor.living_room_co2": 12.0,
        "sensor.living_room_pm25": 1.5,
        "sensor.kitchen_co": 0.5,
    }
    companion_ents = set(canonicalize(e) for e in companions)
    for ent, mag in NOISE.items():
        if ent == trigger_q or ent in companion_ents or ent not in IDX:
            continue
        base = states[IDX[ent]]
        if isinstance(base, (int, float)):
            states[IDX[ent]] = round(base + rng.uniform(-mag, mag), 1)
            if ent not in noise_log["drifted_sensors"]:
                noise_log["drifted_sensors"].append(ent)


def generate_situation(recipe, rng=None):
    """recipe = {
        primary_activity, cause_factory, weather, salience, time_of_day,
        rule_id, service, target, designed_intent, trigger_entity,
        trigger_kind, trigger_above
    }"""
    if rng is None:
        rng = random.Random(recipe.get("noise_seed", 0))

    window_min = recipe.get("window_min", 60)
    base_dt = recipe.get("base_dt", 5)

    # 1. instantiate cause source
    cause = recipe["cause_factory"](rng)
    # slow processes (leak) can request a wider window so their full rise shows
    if getattr(cause, "suggested_window_min", None):
        window_min = max(window_min, cause.suggested_window_min)
        base_dt = max(base_dt, window_min // 12)   # keep ~12-15 grid points

    # 2. sample secondary activity (co-occurrence) -> co_occurring flag
    primary = recipe["primary_activity"]
    secondary = D.sample_secondary(primary, rng)

    # 3. decide snapshot times: grid + forced causal events
    grid = set(range(-window_min, 1, base_dt))
    forced = _forced_times(cause, window_min)
    times = sorted(grid | forced)

    # 4. build each snapshot
    noise_log = {"drifted_sensors": []}
    snapshots = []
    for t in times:
        states = [_default_state(e) for e in DEVICE_SCHEMA]
        # background: primary (and secondary) activity imprints, only while active
        _apply_activity_imprints(states, primary, recipe["salience"], rng)
        if secondary:
            _apply_activity_imprints(states, secondary, recipe["salience"], rng)
        # foreground: cause source drives the trigger quantity + companions
        q = cause.quantity
        # only numeric quantities get value_at written; binary/state triggers
        # are set via companions (motion, group.family, vacuum, etc.)
        if q in IDX and REGISTRY[q]["type"] == "numeric":
            states[IDX[q]] = round(cause.value_at(t), 1)
        for ent, val in cause.companions_at(t).items():
            ent_c = canonicalize(ent)
            if ent_c in IDX:
                states[IDX[ent_c]] = val
        # sleep_mode logical flag for sleep activities
        if primary == "Sleeping" and "input_select.sleep_mode" in IDX:
            states[IDX["input_select.sleep_mode"]] = "on"
        # sensor noise: small drift on numeric sensors that are NOT the trigger
        # quantity and NOT a cause companion (so real readings, not clean ints)
        _apply_sensor_noise(states, q, cause.companions_at(t), rng, noise_log)
        snapshots.append({"t_min_before_trigger": t,
                          "states": states})

    trigger_val = snapshots[-1]["states"][IDX[recipe["trigger_entity"]]]

    situation = {
        "meta": {
            "primary_activity": primary,
            "secondary_activity": secondary,
            "cause_mode": cause.cause_mode,
            "cause_sub_type": cause.sub_type,
            "weather": recipe["weather"],
            "salience": recipe["salience"],
            "_debug_only": True,
        },
        "_ground_facts": {
            # traceability layer: how this situation was generated. Lets anyone
            # reproduce it and verify it is not hand-authored. verdict-agnostic.
            "noise_seed": recipe.get("noise_seed"),
            "cause_mode": cause.cause_mode,
            "cause_sub_type": cause.sub_type,
            "cause_onset_min": round(cause.onset_min, 1),
            "has_human_precursor": bool(cause.companions_at(cause.onset_min + 1)),
            "companion_entities": sorted(set(
                canonicalize(e) for tt in [s["t_min_before_trigger"] for s in snapshots]
                for e in cause.companions_at(tt)
            )),
            "primary_activity": primary,
            "secondary_activity": secondary,
            "co_occurring": secondary is not None,
            "weather": recipe["weather"],
            "weather_role": recipe.get("weather_role"),
            "salience": recipe["salience"],
            "drifted_sensors": noise_log["drifted_sensors"],
            "window_min": window_min,
            "n_snapshots": len(snapshots),
        },
        "device_schema": DEVICE_SCHEMA,
        "snapshots": snapshots,
        "activity": _fill_activity_label(primary, secondary, snapshots, rng),
        "trigger": {
            "entity": recipe["trigger_entity"],
            "kind": recipe["trigger_kind"],
            "above": recipe["trigger_above"],
            "value_now": trigger_val,
        },
        "proposed_action": {
            "rule_id": recipe["rule_id"],
            "service": recipe["service"],
            "target": recipe["target"],
            "designed_intent": recipe["designed_intent"],
        },
    }
    return situation


def _fill_activity_label(primary, secondary, snapshots, rng):
    """LAYER 7 (inlined for now): Plan-B activity field. Single PRIMARY label
    + confidence + last_evidence_t_min + co_occurring flag. NOT a recognizer;
    derived directly from the generation params with a deterministic rule:
    confidence high when primary's deterministic imprints are fresh & present."""
    spec = D.ACTIVITY_SPECTRA[primary]
    det_entities = [canonicalize(e) for e, (tier, _) in spec["imprints"].items()
                    if tier == D.DET]
    last_ev = -999
    schema_idx = {e: i for i, e in enumerate(snapshots[0] and
                  [s for s in range(0)])}  # placeholder; use global IDX
    for snap in snapshots:
        for e in det_entities:
            if e in IDX and snap["states"][IDX[e]] == "on":
                last_ev = max(last_ev, snap["t_min_before_trigger"])
    if last_ev == -999:
        last_ev = -1
    age = -last_ev
    base_conf = 0.9 if det_entities else 0.6
    conf = round(max(0.3, base_conf - 0.02 * age), 2)
    return {
        "label": _label_name(primary),
        "confidence": conf,
        "last_evidence_t_min": last_ev,
        "co_occurring_evidence": secondary is not None,
        "source": "background_sequence_model",
    }


def _label_name(activity):
    """Map internal activity name to the coarser label vocabulary."""
    m = {
        "Cooking": "cooking", "Sleeping": "sleeping", "Taking_a_Shower": "showering",
        "Movie_Night": "watching_tv", "Having_Dinner": "dining",
        "Putting_Baby_to_Sleep": "settling_baby", "Child_Playing_Supervised": "child_playing",
        "Working_From_Home": "working_at_pc", "Evening_Reading": "reading",
        "Night_Activity": "idle", "Idle_At_Home": "idle", "Away": "leaving",
    }
    return m.get(activity, "unknown")


# ---- CO quartet test harness ----
def _co_recipe(primary, cause_factory, weather, salience, seed):
    return {
        "primary_activity": primary,
        "cause_factory": cause_factory,
        "weather": weather,
        "salience": salience,
        "time_of_day": "deep_night",
        "noise_seed": seed,
        "rule_id": "R11",
        "service": "cover.open_cover",
        "target": "cover.kitchen_window",
        "designed_intent": "open kitchen window to ventilate CO",
        "trigger_entity": "sensor.kitchen_co",
        "trigger_kind": "numeric_state",
        "trigger_above": 50,
    }


if __name__ == "__main__":
    quartet = [
        ("S2.4 cooking (coupled)",   "Cooking",  C.co_cooking,    "Sunny_Day",        "typical"),
        ("S2.3 leak (decoupled)",    "Away",     C.co_leak,       "Cloudy_Day",       "typical"),
        ("S2.2 fire (decoupled)",    "Idle_At_Home", C.co_fire,   "Sunny_Day",        "typical"),
        ("S2.1 injection (spurious)","Sleeping", C.co_injection,  "Cold_Clear_Night", "typical"),
    ]
    for tag, prim, fac, wx, sal in quartet:
        sit = generate_situation(_co_recipe(prim, fac, wx, sal, seed=11))
        m = sit["meta"]; a = sit["activity"]
        print("=" * 66)
        print(f"{tag}")
        print(f"  primary={m['primary_activity']} secondary={m['secondary_activity']} "
              f"cause={m['cause_mode']}/{m['cause_sub_type']} weather={m['weather']}")
        print(f"  activity_label={a['label']} conf={a['confidence']} "
              f"last_ev={a['last_evidence_t_min']} co_occur={a['co_occurring_evidence']}")
        print(f"  trigger CO_now={sit['trigger']['value_now']}")
        co_i = IDX["sensor.kitchen_co"]
        km_i = IDX["binary_sensor.kitchen_motion"]
        sm_i = IDX["binary_sensor.kitchen_smoke"]
        tp_i = IDX["sensor.living_room_temperature"]
        print("  CO trajectory:")
        for s in sit["snapshots"]:
            co = s["states"][co_i]
            k = "K" if s["states"][km_i] == "on" else " "
            sm = "S" if s["states"][sm_i] == "on" else " "
            tp = s["states"][tp_i]
            tptag = f"T={tp}" if tp != 21.0 else ""
            bar = "#" * min(36, int(co/5))
            print(f"    t={s['t_min_before_trigger']:>4} CO={co:6.1f} [{k}{sm}] {tptag:<8}{bar}")
