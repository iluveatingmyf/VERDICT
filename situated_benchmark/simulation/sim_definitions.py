# filename: simulation/sim_definitions.py
# ----------------------------------------------------------------------
# LAYER 2 (behaviour) + PHYSICS LAYER (world), built on canonical_registry.
#
# Three tables + one equation skeleton:
#   1. DISPOSITIONS  - where habitual p-values come from (occupant profile)
#   2. WEATHER       - where outdoor physical quantities come from
#   3. ACTIVITY_SPECTRA - each activity as an imprint-generation spectrum
#   4. evolve_quantity() - indoor/outdoor coupling skeleton (interface only)
#
# Design goals this file serves:
#   - NO bare p-value is hand-set. Every probability derives from
#     (disposition profile x salience level). p is a lookup, not a guess.
#   - Difficulty is a controlled axis (salience: clear/typical/subtle), so
#     benchmark conclusions never depend on a single p. You report the curve.
#   - Weather is a physical driver, not a label: opening a window makes the
#     indoor quantity converge toward an outdoor value that the weather sets.
# ----------------------------------------------------------------------

from canonical_registry import REGISTRY, AIR_DOMAIN, ZONE_ADJACENCY, canonicalize

# ======================================================================
# 1. OCCUPANT DISPOSITIONS
# ----------------------------------------------------------------------
# A disposition is a named behavioural tendency of THIS household. Each
# HABITUAL imprint references a disposition; the actual probability is read
# from (disposition x salience). This gives every p a provenance you can
# defend in rebuttal: "0.8 is the nominal value of the 'high-ventilation'
# profile; we ablate the full 0.45-0.9 range via the salience axis."
#
# salience levels:
#   clear   - evidence is abundant (easy case; habitual imprints mostly fire)
#   typical - nominal household behaviour
#   subtle  - evidence is sparse (hard case; habitual imprints often absent)
# ======================================================================
DISPOSITIONS = {
    # Beth cooks with the range hood on most of the time (ventilation-minded).
    "vent_minded":   {"clear": 0.90, "typical": 0.80, "subtle": 0.45},
    # Tidy habit: turning lights off when leaving a room, closing things.
    "tidy":          {"clear": 0.85, "typical": 0.60, "subtle": 0.30},
    # Energy-conscious: dims/lowers things, doesn't leave appliances idle on.
    "energy_saving": {"clear": 0.80, "typical": 0.55, "subtle": 0.25},
    # Comfort-first: uses ambient lighting, secondary devices freely.
    "comfort":       {"clear": 0.75, "typical": 0.55, "subtle": 0.30},
    # Quiet-minded: avoids noisy appliances during rest/baby contexts.
    "quiet_minded":  {"clear": 0.85, "typical": 0.65, "subtle": 0.35},
}

# A single household profile picks which disposition strength is "real" for
# this family. ONE line of narrative per profile = the provenance reviewers
# want. You can swap this to model a different household without touching
# any activity definition.
HOUSEHOLD_PROFILE = {
    "narrative": "Beth ventilates while cooking; both are mildly energy-"
                 "conscious; the home is quiet-minded around the baby.",
    "active_dispositions": ["vent_minded", "energy_saving", "quiet_minded"],
}


def imprint_probability(disposition: str, salience: str) -> float:
    """The only place a habitual p-value is produced. Pure lookup."""
    return DISPOSITIONS[disposition][salience]


# ======================================================================
# 2. WEATHER PHYSICS
# ----------------------------------------------------------------------
# Translate the v20 weather LABELS into actual outdoor physical quantities,
# so opening a window has a physically-determined effect. Every number has
# an obvious physical story (haze = high outdoor PM2.5, cold night = low
# temp + low humidity), so none of it reads as fabricated.
#
# air_exchange = how fast indoor air converges to outdoor when a window is
# open (driven by wind / temperature gradient). Unitless coupling gain.
# ======================================================================
WEATHER = {
    "Sunny_Day":         {"out_pm25": 10,  "out_humidity": 40, "out_temp": 24, "out_co2": 420, "air_exchange": 0.6},
    "Cloudy_Day":        {"out_pm25": 25,  "out_humidity": 55, "out_temp": 20, "out_co2": 420, "air_exchange": 0.4},
    "Hazy_Polluted_Day": {"out_pm25": 160, "out_humidity": 50, "out_temp": 28, "out_co2": 430, "air_exchange": 0.4},
    "Cold_Clear_Night":  {"out_pm25": 15,  "out_humidity": 30, "out_temp": 2,  "out_co2": 415, "air_exchange": 0.6},
    "Rainy_Day":         {"out_pm25": 20,  "out_humidity": 90, "out_temp": 16, "out_co2": 420, "air_exchange": 0.3},
}

# Which outdoor variable each indoor numeric sensor exchanges toward when a
# window in its air-zone is open. (CO and CO2 have ~0 / fixed outdoor levels;
# PM2.5 and humidity are the ones where weather can REVERSE the action.)
OUTDOOR_TARGET = {
    "sensor.kitchen_co":           {"out_key": None,           "out_floor": 0.0},   # outdoor CO ~ 0
    "sensor.living_room_co2":      {"out_key": "out_co2",      "out_floor": 415},
    "sensor.living_room_pm25":     {"out_key": "out_pm25",     "out_floor": None},  # can rise if hazy!
    "sensor.bathroom_humidity":    {"out_key": "out_humidity", "out_floor": None},
    "sensor.living_room_temperature": {"out_key": "out_temp",  "out_floor": None},
}


# ======================================================================
# 3. ACTIVITY IMPRINT SPECTRA
# ----------------------------------------------------------------------
# Each activity = what marks it leaves in the trajectory, in THREE tiers:
#   DETERMINISTIC : physically necessary -> always present (p=1, no number)
#   HABITUAL      : optional, p from (disposition x salience)
#   INCIDENTAL    : weakly correlated -> treated as NOISE, not as evidence
# plus:
#   drift         : numeric quantities this activity nudges (background only;
#                   the cause_mode layer overrides the trigger quantity)
#   presence      : which person(s) this activity implies are home/where
#   time_window   : typical hours (None = no constraint)
#
# This is the GENERATIVE mirror of activities.py's recognition conditions.
# Fixes the Idle_At_Home contradiction (it no longer claims crib=on).
# ======================================================================
DET = "DETERMINISTIC"
HAB = "HABITUAL"
INC = "INCIDENTAL"

ACTIVITY_SPECTRA = {
    "Cooking": {
        "presence": {"person.beth": "home"},
        "time_window": [("07:00", "09:00"), ("17:00", "19:00")],
        "imprints": {
            "binary_sensor.kitchen_motion": (DET, None),  # see note*
            "oven.kitchen_oven":  (HAB, "vent_minded"),
            "switch.range_hood":  (HAB, "vent_minded"),
        },
        "drift": {"sensor.kitchen_co": "slow_up"},  # cause layer may override
        "intent": "Nourishment_and_Sustainment",
    },
    "Taking_a_Shower": {
        "presence": {"person.beth": "home"},
        "time_window": [("07:00", "08:00"), ("21:00", "22:00")],
        "imprints": {
            "binary_sensor.bathroom_motion": (DET, None),
            "light.bathroom_light": (DET, None),
            "fan.bathroom_fan": (HAB, "vent_minded"),
        },
        "drift": {"sensor.bathroom_humidity": "fast_up"},
        "intent": "General_Comfort",
    },
    "Putting_Baby_to_Sleep": {
        "presence": {"person.beth": "home"},
        "time_window": [("19:30", "21:00")],
        "imprints": {
            "binary_sensor.crib_occupancy": (DET, None),
            "light.child_nightlight": (HAB, "comfort"),
            "media_player.living_room_tv": (INC, None),  # sometimes left on low
        },
        "drift": {"sensor.living_room_co2": "slow_up"},  # closed door -> CO2 up
        "intent": "Rest_and_Sleep_Integrity",
    },
    "Child_Playing_Supervised": {
        "presence": {"person.beth": "home"},
        "time_window": [("09:00", "19:00")],
        "imprints": {
            "input_boolean.child_is_active": (DET, None),
            "binary_sensor.living_room_motion": (HAB, "comfort"),
        },
        "drift": {},
        "intent": "Child_Fall_Prevention",
    },
    "Movie_Night": {
        "presence": {"person.alex": "home", "person.beth": "home"},
        "time_window": [("20:00", "23:30")],
        "imprints": {
            "media_player.living_room_tv": (DET, None),
            "light.living_room_light": (HAB, "comfort"),  # dimmed, often on low
        },
        "drift": {},
        "intent": "Entertainment_and_Leisure",
    },
    "Having_Dinner": {
        "presence": {"person.alex": "home", "person.beth": "home"},
        "time_window": [("18:30", "20:00")],
        "imprints": {
            "light.living_room_light": (DET, None),
            "media_player.living_room_tv": (INC, None),  # anti-indicator if on
        },
        "drift": {},
        "intent": "Nourishment_and_Sustainment",
    },
    "Working_From_Home": {
        "presence": {"person.alex": "home"},
        "time_window": [("09:30", "17:30")],
        "imprints": {
            "switch.pc_power": (DET, None),
            "light.study_lamp": (HAB, "comfort"),
            "binary_sensor.bedroom_motion": (INC, None),
        },
        "drift": {},
        "intent": "Focus_and_Creativity",
    },
    "Evening_Reading": {
        "presence": {"person.alex": "home"},
        "time_window": [("21:00", "23:59")],
        "imprints": {
            "binary_sensor.master_bed_occupancy": (DET, None),
            "light.study_lamp": (DET, None),
        },
        "drift": {},
        "intent": "Focus_and_Creativity",
    },
    "Sleeping": {
        "presence": {"person.alex": "home", "person.beth": "home"},
        "time_window": [("22:00", "07:00")],
        "imprints": {
            "binary_sensor.master_bed_occupancy": (DET, None),
            # sleep_mode is the definitive logical trigger, set by generator
        },
        "drift": {},
        "intent": "Rest_and_Sleep_Integrity",
    },
    "Night_Activity": {
        "presence": {"person.alex": "home"},   # at least one; OR-handled by generator
        "time_window": [("00:00", "05:00")],
        "imprints": {
            "binary_sensor.living_room_motion": (HAB, "comfort"),
            "light.living_room_light": (HAB, "comfort"),
        },
        "drift": {},
        "intent": "General_Comfort",
    },
    "Idle_At_Home": {
        # FIXED: no longer claims crib=on. True default low-priority state:
        # someone is home, no specific activity signature.
        "presence": {"person.alex": "home"},
        "time_window": None,
        "imprints": {},          # the absence of strong imprints IS the signature
        "drift": {},
        "intent": "General_Comfort",
        "priority": "lowest",    # generator picks this only when nothing else fits
    },
    "Away": {
        "presence": {"person.alex": "not_home", "person.beth": "not_home"},
        "time_window": None,
        "imprints": {},
        "drift": {},
        "intent": "Security_Physical_Integrity",
    },
}
# *NOTE: kitchen motion has no canonical entity yet in the registry (the
#  floor plan shows motion sensors 4x but kitchen motion isn't separately
#  listed). FLAGGED as open question Q5 below.


# ======================================================================
# 4. INDOOR/OUTDOOR COUPLING  (equation skeleton - interface only)
# ----------------------------------------------------------------------
# The generator (Layer 4) will integrate this. Here we fix the FORM so the
# behaviour, cause, and weather layers all plug into one equation:
#
#   d(Q)/dt = source(t)            # from activity drift + cause_mode source
#           - decay * (Q - floor)  # natural settling
#           - k_exch * window_open * air_exchange * (Q - Q_outdoor)
#
# The third term is the physics you asked for: with a window open, Q is
# pulled toward Q_outdoor at a rate set by the weather. For PM2.5 on a hazy
# day, Q_outdoor > Q_indoor, so the term ADDS pm25 -> opening the window
# makes it worse. That single sign flip is what makes S2.5/6 physically real.
# ======================================================================
def evolve_quantity(entity_id, Q, source_rate, window_open, weather_label, dt):
    """Skeleton. Returns next-step value of a numeric quantity.
    Full numerical implementation belongs to the generator (Layer 4)."""
    entity_id = canonicalize(entity_id)
    tgt = OUTDOOR_TARGET.get(entity_id)
    if tgt is None:
        return Q + source_rate * dt  # non-coupled quantity
    w = WEATHER[weather_label]
    if tgt["out_key"] is None:
        q_out = tgt["out_floor"]            # e.g. outdoor CO ~ 0
    else:
        q_out = w[tgt["out_key"]]
    decay = 0.02
    k_exch = 0.05
    exchange = k_exch * (1.0 if window_open else 0.0) * w["air_exchange"] * (Q - q_out)
    floor = tgt["out_floor"] if tgt["out_floor"] is not None else q_out
    dQ = source_rate - decay * (Q - floor) - exchange
    return Q + dQ * dt


if __name__ == "__main__":
    print("DISPOSITIONS:", list(DISPOSITIONS))
    print("Active household profile:", HOUSEHOLD_PROFILE["active_dispositions"])
    print("WEATHER labels:", list(WEATHER))
    print("ACTIVITY_SPECTRA:", len(ACTIVITY_SPECTRA), "activities")
    print()
    # demo: the PM2.5 sign-flip that makes opening a window WORSE on hazy day
    print("Window-open PM2.5 demo (indoor starts 80):")
    for wl in ["Sunny_Day", "Hazy_Polluted_Day"]:
        Q = 80.0
        for _ in range(10):
            Q = evolve_quantity("sensor.living_room_pm25", Q, 0, True, wl, 1.0)
        arrow = "down (vent works)" if Q < 80 else "UP (vent backfires)"
        print(f"  {wl:<18} after 10 min open window: {Q:5.1f}  -> {arrow}")
    print()
    # demo: habitual p provenance
    print("range_hood p across salience (vent_minded profile):")
    for s in ["clear", "typical", "subtle"]:
        print(f"  {s:<8} p={imprint_probability('vent_minded', s)}")


# ======================================================================
# 5. CO-OCCURRENCE MATRIX  (Layer 3)
# ----------------------------------------------------------------------
# Under Plan B: one PRIMARY activity + a co_occurring flag. This matrix says
# which (primary, secondary) activity pairs can happen together, AND with
# what likelihood. The probability is NOT hand-picked; it's derived from:
#   - same_person?   two activities by the SAME person can't co-occur -> 0
#   - time overlap?  if their typical windows don't overlap -> low/0
#   - logical bond?  activities that naturally accompany each other -> high
#   - mode exclusion? sleep_mode on/off etc. makes some pairs impossible -> 0
#
# Value = P(secondary is also happening | primary is happening). Used to:
#   (a) decide whether to set co_occurring_evidence flag
#   (b) sample realistic households (common pairs generated more often)
# Only NON-ZERO, non-trivial pairs are listed; unlisted pair => 0 (exclusive
# or never co-occurs). Matrix is asymmetric: P(B|A) != P(A|B) in general.
# ======================================================================

# Mode/logic exclusions that force 0 regardless of timing:
#   Sleeping (sleep_mode=on) excludes everything needing sleep_mode=off
#   Away excludes every AT_HOME activity
#   same person can't do two things at once
MUTEX_REASON = {
    ("Sleeping", "Movie_Night"): "sleep_mode on vs off",
    ("Sleeping", "Cooking"): "sleep_mode on; also no transition sleep->cook",
    ("Sleeping", "Having_Dinner"): "sleep_mode on vs off",
    ("Away", "*"): "nobody home",
}

# P(secondary | primary). Derived, with one-line provenance each.
CO_OCCURRENCE = {
    "Sleeping": {
        # Alex+Beth both in bed (sleep_mode on). Baby in crib is the common
        # co-occurring source. Cooking by a third party is the RARE anomaly
        # (this is exactly the S2.x night-CO conflict — kept low but nonzero).
        "Putting_Baby_to_Sleep": 0.15,   # one parent may still be settling baby
        "Night_Activity":        0.10,   # one wakes for a midnight errand
    },
    "Putting_Baby_to_Sleep": {
        # Beth soothes baby; Alex may independently watch TV or read.
        "Movie_Night":     0.20,   # Alex watching while Beth puts baby down
        "Evening_Reading": 0.25,   # quiet co-activity, time windows overlap
        "Working_From_Home": 0.05, # late work, rare
    },
    "Cooking": {
        # Beth cooks; co-occurring sources around dinnertime.
        "Child_Playing_Supervised": 0.35,  # kid plays while parent cooks — common
        "Working_From_Home":        0.10,  # Alex still working pre-dinner
        "Movie_Night":              0.05,  # rare, TV pre-dinner
    },
    "Movie_Night": {
        # Both on couch. Baby asleep in crib is the common companion state.
        "Putting_Baby_to_Sleep": 0.10,  # tail end, baby just down
    },
    "Having_Dinner": {
        "Child_Playing_Supervised": 0.20,  # kid in/out during dinner
    },
    "Working_From_Home": {
        "Child_Playing_Supervised": 0.30,  # Alex works, Beth+kid present
        "Taking_a_Shower":          0.10,
    },
    "Child_Playing_Supervised": {
        "Cooking":           0.40,  # parent cooks while supervising — very common
        "Working_From_Home": 0.25,
        "Taking_a_Shower":   0.08,
    },
    "Evening_Reading": {
        "Putting_Baby_to_Sleep": 0.20,
    },
    "Night_Activity": {
        "Sleeping": 0.40,  # one person up, the other still asleep — common
    },
    "Idle_At_Home": {
        # default state; many things can be weakly co-occurring
        "Child_Playing_Supervised": 0.30,
        "Cooking":                  0.15,
    },
}


def co_occurrence_prob(primary: str, secondary: str) -> float:
    """P(secondary also happening | primary). 0 if mutex/unlisted."""
    if primary == secondary:
        return 0.0
    return CO_OCCURRENCE.get(primary, {}).get(secondary, 0.0)


def sample_secondary(primary: str, rng):
    """Sample whether a secondary activity co-occurs, weighted by likelihood.
    Returns secondary activity name or None. This is where co_occurring_evidence
    gets its realistic distribution."""
    candidates = CO_OCCURRENCE.get(primary, {})
    for sec, p in candidates.items():
        if rng.random() < p:
            return sec   # first hit wins (rare to have >1 secondary)
    return None
