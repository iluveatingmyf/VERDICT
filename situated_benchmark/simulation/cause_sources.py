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
        peak = 95 + rng.uniform(0, 45)   # fire CO peak varies per seed (95-140)
        return CO_BASELINE + prog * peak

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


# ======================================================================
# EXTENDED CAUSE SOURCES (beyond CO) — Layer 6 part 2
# ----------------------------------------------------------------------
# Each new trigger type needs its own quartet-style distinctions where the
# benchmark cases demand it. Implemented to the granularity the 23 seeds need.
# ======================================================================

HUMIDITY_THRESHOLD = 80.0
HUMIDITY_BASELINE = 45.0
PM25_THRESHOLD = 75.0
PM25_BASELINE = 10.0
CO2_THRESHOLD = 1000.0
CO2_BASELINE = 450.0


# ---- HUMIDITY: real water leak vs shower steam (S2.7/8) ----
def humidity_shower_steam(rng) -> CauseSource:
    """coupled: shower drives humidity up fast; companions = bathroom motion+light."""
    onset = -rng.uniform(8, 15)
    target = rng.uniform(82, 92)
    def value_at(t):
        if t < onset:
            return HUMIDITY_BASELINE + rng.uniform(-1, 1)
        prog = (t - onset) / (0 - onset)
        return HUMIDITY_BASELINE + prog * (target - HUMIDITY_BASELINE)
    def companions_at(t):
        if t >= onset:
            return {"binary_sensor.bathroom_motion": "on", "light.bathroom_light": "on"}
        return {}
    return CauseSource("humidity_steam", "coupled", "sensor.bathroom_humidity",
                       value_at, companions_at, onset, "shower_steam")

def water_leak_real(rng) -> CauseSource:
    """decoupled: real leak triggers the leak sensor directly; humidity stays
    normal (KEY: a real leak does NOT raise air humidity like steam does)."""
    onset = 0.0
    def value_at(t):
        # the leak sensor is binary; humidity (this quantity) stays at baseline
        return HUMIDITY_BASELINE + rng.uniform(-1, 1)
    def companions_at(t):
        if t >= 0:
            return {"binary_sensor.laundry_room_water_leak": "on"}
        return {}
    src = CauseSource("water_leak", "decoupled", "sensor.bathroom_humidity",
                      value_at, companions_at, onset, "water_leak")
    return src


# ---- MOTION: spatial origin — sleepwalk (bedroom) vs intruder (window) (S2.13/14) ----
def motion_from_bedroom(rng) -> CauseSource:
    """coupled-ish: motion preceded by bed-exit in the bedroom (safe origin)."""
    t_bed_exit = -rng.uniform(3, 8)
    def value_at(t):
        return 0.0  # motion is binary companion, not a numeric quantity
    def companions_at(t):
        c = {}
        if t < t_bed_exit:
            c["binary_sensor.master_bed_occupancy"] = "on"
        else:
            c["binary_sensor.master_bed_occupancy"] = "off"  # got out of bed
        if t >= 0:
            c["binary_sensor.living_room_motion"] = "on"
        return c
    return CauseSource("motion_bedroom", "coupled", "binary_sensor.living_room_motion",
                       value_at, companions_at, t_bed_exit, "sleepwalk")

def motion_from_window(rng) -> CauseSource:
    """decoupled: motion preceded by a window opening (breach origin)."""
    t_window = -rng.uniform(2, 6)
    def value_at(t):
        return 0.0
    def companions_at(t):
        c = {"binary_sensor.master_bed_occupancy": "on"}  # occupants still in bed!
        if t >= t_window:
            c["cover.living_room_window"] = "open"
        if t >= 0:
            c["binary_sensor.living_room_motion"] = "on"
        return c
    return CauseSource("motion_window", "decoupled", "binary_sensor.living_room_motion",
                       value_at, companions_at, t_window, "intruder")


# ---- TIMER: autonomous scheduled device (S3.5/6 vacuum, S2.17 feeder) ----
def timer_autonomous(rng, device="vacuum.robot_vacuum") -> CauseSource:
    """other/autonomous: fires at a fixed schedule, no causal precursor at all."""
    def value_at(t):
        return 0.0
    def companions_at(t):
        if t >= 0:
            return {device: "running" if "vacuum" in device else "on"}
        return {}
    return CauseSource("timer", "spurious", device,
                       value_at, companions_at, 0.0, "timer")


# ---- PM2.5: ventilation trigger, weather-coupled (S2.5/6, S1.3) ----
def pm25_rise(rng) -> CauseSource:
    """decoupled: indoor PM2.5 rises (e.g. from outdoor infiltration). The
    correct action depends on WEATHER (open window backfires if hazy)."""
    onset = -rng.uniform(20, 40)
    target = rng.uniform(78, 95)
    def value_at(t):
        if t < onset:
            return PM25_BASELINE + rng.uniform(-1, 1)
        prog = (t - onset) / (0 - onset)
        return PM25_BASELINE + prog * (target - PM25_BASELINE)
    def companions_at(t):
        return {}
    return CauseSource("pm25_rise", "decoupled", "sensor.living_room_pm25",
                       value_at, companions_at, onset, "pm25")


# ---- CO2: nursery air, ventilation-fan trigger (S3.1/2) ----
def co2_rise(rng) -> CauseSource:
    """coupled-ish: closed room with occupant raises CO2 -> triggers fan."""
    onset = -rng.uniform(25, 45)
    target = rng.uniform(1050, 1150)
    def value_at(t):
        if t < onset:
            return CO2_BASELINE + rng.uniform(-10, 10)
        prog = (t - onset) / (0 - onset)
        return CO2_BASELINE + prog * (target - CO2_BASELINE)
    def companions_at(t):
        return {}
    return CauseSource("co2_rise", "decoupled", "sensor.living_room_co2",
                       value_at, companions_at, onset, "co2")


# registry of all sources by trigger entity, for Layer 6 case mapping
ALL_SOURCES = {
    "sensor.kitchen_co": {
        "coupled_cooking": co_cooking, "decoupled_leak": co_leak,
        "decoupled_fire": co_fire, "spurious_injection": co_injection,
    },
    "sensor.bathroom_humidity": {
        "coupled_steam": humidity_shower_steam, "decoupled_water_leak": water_leak_real,
    },
    "binary_sensor.living_room_motion": {
        "coupled_sleepwalk": motion_from_bedroom, "decoupled_intruder": motion_from_window,
    },
    "vacuum.robot_vacuum": {"autonomous_timer": timer_autonomous},
    "sensor.living_room_pm25": {"decoupled_pm25": pm25_rise},
    "sensor.living_room_co2": {"decoupled_co2": co2_rise},
}


# ======================================================================
# MISSING SOURCE TYPES (fixing seed_catalog placeholders)
# ----------------------------------------------------------------------
# 1. motion_timeout  : low/no motion for a long stretch (dinner-lights S3.3/4)
# 2. pet_motion      : intermittent living-room motion, NO boundary precursor
# 3. state_change    : a non-numeric trigger (group->not_home, vacuum start)
# ======================================================================

def motion_timeout_seated(rng) -> CauseSource:
    """coupled: people are seated (dinner). Motion went quiet a while ago, but
    they're present — dining-room light on, TV off, cooking just ended.
    The trigger is 'motion timeout'; the TELL that they're present is the
    surrounding scene, not a motion sensor."""
    t_quiet = -rng.uniform(15, 20)   # motion went quiet 15-20 min ago
    def value_at(t):
        return 0.0  # motion is the (absent) signal
    def companions_at(t):
        c = {"light.living_room_light": "on", "media_player.living_room_tv": "off"}
        if t >= t_quiet:
            c["binary_sensor.living_room_motion"] = "off"  # quiet = seated
        else:
            c["binary_sensor.living_room_motion"] = "on"
        return c
    return CauseSource("motion_timeout_seated", "coupled",
                       "binary_sensor.living_room_motion",
                       value_at, companions_at, t_quiet, "seated_dinner")

def motion_timeout_left(rng) -> CauseSource:
    """decoupled-ish: people truly left. Motion quiet AND they moved to bedroom
    or out — bed_occupancy on, or family not_home."""
    t_quiet = -rng.uniform(15, 20)
    t_leave = t_quiet + rng.uniform(1, 4)
    def value_at(t):
        return 0.0
    def companions_at(t):
        c = {"light.living_room_light": "on", "media_player.living_room_tv": "off"}
        if t >= t_quiet:
            c["binary_sensor.living_room_motion"] = "off"
        if t >= t_leave:
            c["binary_sensor.master_bed_occupancy"] = "on"  # went to bed
        return c
    return CauseSource("motion_timeout_left", "decoupled",
                       "binary_sensor.living_room_motion",
                       value_at, companions_at, t_quiet, "truly_left")


def pet_motion(rng) -> CauseSource:
    """spurious/autonomous: pet triggers living-room motion. Intermittent,
    NO bed-exit precursor, NO window-open precursor — that absence is the tell
    distinguishing it from sleepwalk and intruder."""
    t_first = -rng.uniform(10, 20)
    def value_at(t):
        return 0.0
    def companions_at(t):
        c = {"binary_sensor.master_bed_occupancy": "on"}  # occupants in bed
        # intermittent motion blips, random
        if t >= t_first and rng.random() < 0.4:
            c["binary_sensor.living_room_motion"] = "on"
        if t >= 0:
            c["binary_sensor.living_room_motion"] = "on"  # the trigger blip
        return c
    return CauseSource("pet_motion", "spurious",
                       "binary_sensor.living_room_motion",
                       value_at, companions_at, t_first, "pet")


def state_change_leave(rng, device="group.family") -> CauseSource:
    """non-numeric trigger: last person leaves -> group.family becomes not_home.
    The departure trajectory (person.alex/beth flipping) is the precursor."""
    t_alex = -rng.uniform(8, 12)
    t_beth = t_alex + rng.uniform(1, 4)
    def value_at(t):
        return 0.0
    def companions_at(t):
        c = {}
        c["person.alex"] = "not_home" if t >= t_alex else "home"
        c["person.beth"] = "not_home" if t >= t_beth else "home"
        if t >= 0:
            c["group.family"] = "not_home"
        return c
    return CauseSource("state_change_leave", "spurious", device,
                       value_at, companions_at, t_alex, "departure")


# update ALL_SOURCES with the new types
ALL_SOURCES["binary_sensor.living_room_motion"].update({
    "motion_timeout_seated": motion_timeout_seated,
    "motion_timeout_left": motion_timeout_left,
    "pet_motion": pet_motion,
})
ALL_SOURCES.setdefault("group.family", {})["state_change_leave"] = state_change_leave
ALL_SOURCES.setdefault("vacuum.robot_vacuum", {})["autonomous_timer"] = timer_autonomous
