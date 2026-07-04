# filename: simulation/activity_coupling.py
# ----------------------------------------------------------------------
# LAYER 6 (part 1): CAUSE -> ACTIVITY COUPLING + LEGAL-ACTIVITY SOLVER
#
# The fix for "a CO leak can happen while the user does ANYTHING".
#
# cause_mode determines whether the activity is LOCKED or FREE:
#   coupled    -> activity is LOCKED to the activity that causes the trigger
#                 (cooking CO must come with Cooking)
#   decoupled  -> activity is FREE (leak/fire don't care what the user does)
#   spurious   -> activity is FREE (injection is independent of activity)
# EXCEPT: a case may pin the activity for semantic reasons (S2.1 injection
#         is specifically "spoofed WHILE ASLEEP") -> pin overrides freedom.
#
# When FREE, "free" != "anything". Three constraints filter the legal set:
#   C1 time-consistency : activity's time_window must contain time_of_day
#   C2 physical non-interference : exclude activities that would FORGE the
#      cause's own evidence (a CO leak must not co-occur with Cooking, else
#      kitchen CO evidence appears and the leak looks like cooking)
#   C3 presence-consistency : activity presence must match the scenario
#      (an Away leak can't co-occur with an at-home activity)
# ----------------------------------------------------------------------

from datetime import time as _t
import sim_definitions as D

# Map a coarse time-of-day to a representative clock time for window checks.
TIME_OF_DAY_CLOCK = {
    "morning":    _t(8, 0),
    "midday":     _t(12, 30),
    "evening":    _t(19, 0),
    "night":      _t(22, 30),
    "deep_night": _t(3, 0),
}

# Which cause sub_types FORGE evidence that a given activity also produces.
# If the activity is in this set for a cause, including it would make the
# decoupled/spurious trigger look coupled -> exclude it (constraint C2).
CAUSE_FORGED_BY_ACTIVITY = {
    # a kitchen-CO leak/injection must NOT co-occur with Cooking (Cooking
    # produces kitchen CO + motion, which would masquerade as the cause)
    "leak":      {"sensor.kitchen_co": ["Cooking"]},
    "injection": {"sensor.kitchen_co": ["Cooking"]},
    "fire":      {"sensor.kitchen_co": ["Cooking"]},
    # a humidity leak (water) vs shower steam: a real water leak must NOT
    # co-occur with Taking_a_Shower (steam would forge the humidity evidence)
    "water_leak": {"sensor.bathroom_humidity": ["Taking_a_Shower"]},
}


def _clock_in_window(clock, window):
    """Handle windows that may wrap past midnight (e.g. 22:00-07:00)."""
    start_s, end_s = window
    sh, sm = map(int, start_s.split(":"))
    eh, em = map(int, end_s.split(":"))
    start, end = _t(sh, sm), _t(eh, em)
    if start <= end:
        return start <= clock <= end
    return clock >= start or clock <= end   # wraps midnight


def _activity_allows_time(activity, time_of_day):
    spec = D.ACTIVITY_SPECTRA[activity]
    windows = spec.get("time_window")
    if windows is None:
        return True                          # no constraint (Idle, Away)
    clock = TIME_OF_DAY_CLOCK[time_of_day]
    return any(_clock_in_window(clock, w) for w in windows)


def _activity_presence_ok(activity, scenario_presence):
    """scenario_presence e.g. {'group.family':'not_home'} for Away leak.
    Activity is OK if its presence doesn't contradict the scenario."""
    spec = D.ACTIVITY_SPECTRA[activity]
    for ent, val in spec["presence"].items():
        if ent in scenario_presence and scenario_presence[ent] != val:
            return False
    # if scenario says nobody home, exclude any activity requiring someone home
    if scenario_presence.get("group.family") == "not_home":
        for ent, val in spec["presence"].items():
            if ent.startswith("person.") and val == "home":
                return False
        if activity != "Away":
            return False
    return True


def legal_activities(cause_sub_type, trigger_entity, time_of_day,
                     scenario_presence=None):
    """Return the set of activities that can LEGALLY co-occur with this cause.
    This is the 'general combination logic' you asked for."""
    scenario_presence = scenario_presence or {}
    forged = CAUSE_FORGED_BY_ACTIVITY.get(cause_sub_type, {}).get(trigger_entity, [])
    legal = []
    for act in D.ACTIVITY_SPECTRA:
        if act in forged:
            continue                                   # C2: would forge evidence
        if not _activity_allows_time(act, time_of_day):
            continue                                   # C1: time-inconsistent
        if not _activity_presence_ok(act, scenario_presence):
            continue                                   # C3: presence-inconsistent
        legal.append(act)
    return legal


def resolve_activity(cause_mode, cause_sub_type, trigger_entity, time_of_day,
                     rng, pinned_activity=None, locked_activity=None,
                     scenario_presence=None):
    """Decide the PRIMARY activity for a situation.
      - pinned_activity   : case semantically fixes it (highest priority)
      - locked_activity   : coupled cause fixes it (e.g. Cooking for cooking CO)
      - otherwise FREE    : sample from legal_activities by time-prior
    Returns (primary_activity, legal_set)."""
    if pinned_activity:
        return pinned_activity, [pinned_activity]
    if cause_mode == "coupled" and locked_activity:
        return locked_activity, [locked_activity]
    legal = legal_activities(cause_sub_type, trigger_entity, time_of_day,
                             scenario_presence)
    if not legal:
        legal = ["Idle_At_Home"]
    # time-prior: weight by how central this time is to the activity (simple:
    # uniform here, but Idle/Night get a floor so they're always possible)
    primary = rng.choice(legal)
    return primary, legal


if __name__ == "__main__":
    import random
    rng = random.Random(0)
    print("LEGAL ACTIVITY SETS by (cause, time):\n")
    scenarios = [
        ("leak", "sensor.kitchen_co", "deep_night", {}, "CO leak at 3am"),
        ("leak", "sensor.kitchen_co", "evening", {}, "CO leak in evening"),
        ("injection", "sensor.kitchen_co", "deep_night", {}, "CO injection at 3am"),
        ("leak", "sensor.kitchen_co", "evening", {"group.family": "not_home"}, "CO leak while Away"),
        ("water_leak", "sensor.bathroom_humidity", "evening", {}, "water leak evening"),
    ]
    for sub, ent, tod, pres, desc in scenarios:
        legal = legal_activities(sub, ent, tod, pres)
        print(f"  {desc}:")
        print(f"    -> {legal}\n")

    print("RESOLVE demo (free cause samples different activities per seed):")
    for seed in range(6):
        r = random.Random(seed)
        act, _ = resolve_activity("decoupled", "leak", "sensor.kitchen_co",
                                  "evening", r)
        print(f"    seed={seed}: leak co-occurs with activity = {act}")
