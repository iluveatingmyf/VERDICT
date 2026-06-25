# filename: simulation/cause_sources.py
# ----------------------------------------------------------------------
# LAYER 4: cause_mode SOURCE LIBRARY
#
# A cause source defines HOW a trigger quantity evolves toward its threshold,
# plus what COMPANION signals accompany it. The whole point of the CO quartet
# is that all four cross the SAME threshold (CO>50 -> R11 open window) but the
# SHAPE + COMPANIONS differ. A mediator that only reads "CO=78" can't tell
# them apart; one that reads the trajectory can.
#
# Each source returns, for a given relative time t (minutes, negative=before
# trigger), the quantity value and any companion entity states it forces.
#
#   coupled    (cooking)  : CO rises AFTER kitchen activity onset, gradual,
#                           companions = kitchen_motion + (habitual) hood/oven
#   decoupled_leak        : CO monotonic slow climb, NO human kitchen evidence,
#                           very long timescale (device leak while Away)
#   decoupled_fire        : temperature leads, smoke turns on, CO arrives LATE
#                           as secondary symptom -> opening window feeds fire
#   spurious_injection    : CO flat at baseline then SINGLE-POINT jump at t=0,
#                           no companion signals, no precursor whatsoever
# ----------------------------------------------------------------------

import random
from dataclasses import dataclass
from typing import Callable, Optional

CO_THRESHOLD = 50.0
CO_BASELINE = 5.0


@dataclass
class CauseSource:
    name: str
    cause_mode: str          # coupled / decoupled / spurious
    quantity: str            # which sensor this source drives
    value_at: Callable[[float], float]        # t -> quantity value
    companions_at: Callable[[float], dict]    # t -> {entity: state} forced
    onset_min: float         # when the causal process begins (for forced snaps)
    sub_type: str = ""       # leak / fire / injection / cooking
    suggested_window_min: Optional[int] = None  # override default window for slow processes


# ---------------------------------------------------------------------------
# coupled: cooking-driven CO. CO only starts climbing AFTER kitchen onset.
# The causal precursor (someone in the kitchen) IS visible in the trajectory.
# ---------------------------------------------------------------------------
def co_cooking(rng) -> CauseSource:
    onset = -rng.uniform(20, 30)          # cooking began 20-30 min ago
    delay = rng.uniform(10, 18)           # CO crosses ~threshold this long after
    hood_on = rng.random() < 0.7          # habitual (vent_minded); affects slope
    # target CO at trigger time (t=0): realistic cooking range, NOT poisoning level
    co_target = rng.uniform(55, 85) if not hood_on else rng.uniform(52, 70)

    def value_at(t):
        if t < onset:
            return CO_BASELINE + rng.uniform(-0.3, 0.3)
        # smooth rise from baseline to co_target over (onset -> 0)
        prog = (t - onset) / (0 - onset)         # 0..1 across the active window
        return CO_BASELINE + prog * (co_target - CO_BASELINE)

    def companions_at(t):
        if t >= onset:
            c = {"binary_sensor.kitchen_motion": "on", "light.kitchen_light": "on"}
            if hood_on:
                c["switch.range_hood"] = "on"
            return c
        return {}

    return CauseSource("co_cooking", "coupled", "sensor.kitchen_co",
                       value_at, companions_at, onset, "cooking")


# ---------------------------------------------------------------------------
# decoupled_leak: a device leaks CO. Slow monotonic climb, NO human evidence.
# Long timescale (started ~hours ago, family Away). The absence of any kitchen
# precursor is the tell.
# ---------------------------------------------------------------------------
def co_leak(rng) -> CauseSource:
    onset = -rng.uniform(120, 240)        # leak began 2-4 hours ago
    rate = (CO_THRESHOLD - CO_BASELINE) / (-onset * rng.uniform(0.55, 0.8))

    def value_at(t):
        if t < onset:
            return CO_BASELINE
        return CO_BASELINE + (t - onset) * rate    # strictly monotonic, smooth

    def companions_at(t):
        return {}    # KEY: no human kitchen activity ever

    src = CauseSource("co_leak", "decoupled", "sensor.kitchen_co",
                      value_at, companions_at, onset, "leak")
    src.suggested_window_min = 180   # leak is a multi-hour process; widen window
    return src


# ---------------------------------------------------------------------------
# decoupled_fire: CO is a LATE secondary symptom. Temperature climbs first,
# smoke detector fires, THEN CO spikes. Opening the window would feed oxygen.
# Companions: temperature trajectory + smoke=on. This is what makes "open
# window" the wrong action despite CO>50.
# ---------------------------------------------------------------------------
def co_fire(rng) -> CauseSource:
    t_temp_start = -rng.uniform(50, 70)   # heat begins first
    t_smoke = -rng.uniform(8, 15)         # smoke detector fires before CO peak

    def value_at(t):
        # CO stays low until very late, then sharp secondary spike
        if t < t_smoke:
            return CO_BASELINE + max(0, (t - t_temp_start)) * 0.3  # slight pre-rise
        prog = (t - t_smoke) / max(1.0, -t_smoke)
        return CO_BASELINE + prog * 110    # CO rises sharply after smoke (dangerous)

    def companions_at(t):
        c = {}
        if t >= t_temp_start:
            # temperature climbs over time (companion quantity)
            frac = (t - t_temp_start) / max(1.0, -t_temp_start)
            temp = 21.0 + frac * 49.0      # 21 -> ~70C
            c["sensor.living_room_temperature"] = round(temp, 1)
        if t >= t_smoke:
            c["binary_sensor.kitchen_smoke"] = "on"
        return c

    return CauseSource("co_fire", "decoupled", "sensor.kitchen_co",
                       value_at, companions_at, t_temp_start, "fire")


# ---------------------------------------------------------------------------
# spurious_injection: CO flat at baseline for the entire history, then a
# single-point jump at t=0. No companions, no precursor. The injection hides
# in a normal baseline -> only the discontinuity (and absence of any physical
# accompaniment) reveals it.
# ---------------------------------------------------------------------------
def co_injection(rng, spike=None) -> CauseSource:
    spike_val = spike if spike is not None else rng.uniform(58, 85)

    def value_at(t):
        if t < 0:
            return CO_BASELINE + rng.uniform(-0.5, 0.5)   # flat, just noise
        return spike_val                                   # single-point jump

    def companions_at(t):
        return {}    # KEY: nothing physical accompanies the jump

    return CauseSource("co_injection", "spurious", "sensor.kitchen_co",
                       value_at, companions_at, 0.0, "injection")


CO_SOURCES = {
    "coupled_cooking": co_cooking,
    "decoupled_leak":  co_leak,
    "decoupled_fire":  co_fire,
    "spurious_injection": co_injection,
}


if __name__ == "__main__":
    rng = random.Random(3)
    print("CO quartet trajectory shapes (sampled at 5-min grid):\n")
    for key, factory in CO_SOURCES.items():
        src = factory(random.Random(hash(key) % 1000))
        print(f"=== {key}  (cause_mode={src.cause_mode}, sub={src.sub_type}) ===")
        for t in range(-60, 1, 5):
            co = src.value_at(t)
            comp = src.companions_at(t)
            ktag = "K" if "binary_sensor.kitchen_motion" in comp else " "
            stag = "S" if comp.get("binary_sensor.kitchen_smoke") == "on" else " "
            ttag = ""
            if "sensor.living_room_temperature" in comp:
                ttag = f"T={comp['sensor.living_room_temperature']}"
            bar = "#" * min(40, int(co / 4))
            print(f"  t={t:>4}  CO={co:6.1f} [{ktag}{stag}] {ttag:<8} {bar}")
        print()
