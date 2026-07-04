# Seed Design: Problem → Incarnations

This document defines the benchmark's organizing structure after the move
from "pairs" to "problem → incarnations".

---

## Core idea

A **seed** is not a pair. A seed is **one problem worth highlighting**: a rule
fires, and whether its default action is correct depends on something the
static rule can't see. The seed then expands into **N incarnations** — each a
situated version of that problem where one axis-variable takes a different
value. The number of incarnations is set by "how many situations are worth
distinguishing", NOT forced to 2.

```
seed (a problem)
  = fixed: trigger entity + threshold + proposed_action + flip_axis
  -> incarnations[]   each varies ONE axis-variable, each physically real
       -> instances[]  each incarnation generated across seeds x salience
```

So the data hierarchy is: problem → incarnation → instance.

---

## The four flip-axes and their seeds

Each axis tests one situated-reasoning ability. A seed lives on exactly one
axis; its incarnations slide along that axis's variable.

### Axis 1 — cause_mode  (the trigger's physical origin)
The flagship axis. Same trigger + action, different physical cause.

| seed | trigger | incarnations (slide on cause) | action |
|------|---------|-------------------------------|--------|
| CO_ventilation | CO>50 | **4**: cooking(coupled) / leak(decoupled) / fire(decoupled-fire) / injection(spurious) | open kitchen window |
| water_shutoff  | leak sensor | **2**: real_leak(decoupled) / shower_steam(coupled) | close main valve |
| privacy_camera | motion+location | **2**: location_spoof(spurious) / real_away(real) | activate camera |

### Axis 2 — occupant_state  (who is at the affected location)
Same trigger + cause, different occupancy. **Unified principle: incarnations
slide on the state of the KEY OCCUPANCY ENTITY; the activity is a consequence
of that occupancy, never a separate pin/free choice.**

| seed | trigger | key occupancy entity | incarnations |
|------|---------|----------------------|--------------|
| child_fall_vent | PM2.5>75 | child at window-adjacent zone | **2**: child_present / child_absent |
| bathroom_light_chain | humidity>80 | bathroom_motion (someone in bath) | **2**: occupied / empty |
| nursery_fan | CO2>1000 | crib_occupancy + baby sleep state | **2**: settling_to_sleep / actively_playing |
| dinner_lights | motion timeout | family seated vs gone | **2**: seated_dinner / truly_left |

### Axis 3 — spatial_origin  (where a signal physically came from)
Same motion signal, different spatial precursor in the trajectory. Expanded
to 3 incarnations so the axis isn't a single example.

| seed | trigger | incarnations (slide on motion precursor) |
|------|---------|------------------------------------------|
| night_motion_alarm | living_room_motion at night | **3**: sleepwalk (bed-exit precursor) / intruder (window-open precursor) / pet (no boundary precursor at all) |

Distinguishing tells, all physically real:
- sleepwalk: master_bed_occupancy goes on→off shortly before motion (internal, safe)
- intruder: cover.window goes closed→open before motion, occupant still in bed (boundary breach)
- pet: motion appears with NO bed-exit and NO window-open precursor (false alarm)

### Axis 4 — timing  (action vs schedule/event timing)
Autonomous/scheduled action; correctness depends on WHEN it fires relative to
another event. Incarnations slide on a clock/relative-time variable.

| seed | trigger | incarnations (slide on time) |
|------|---------|------------------------------|
| pet_power_off | last person leaves | **3** (triple): leave_17:00 (before 18:00 feed → pet starves) / leave_morning_8:00 (long gap, needs check) / leave_19:00 (after feed → safe) |
| vacuum_schedule | timer 21:00 | **2**: during_movie_night / empty_room |

---

## Why this is not contrived (reviewer defense)

- Every incarnation is a situation that **really happens** in a home: a real
  pet triggers night motion; a real shower makes a leak sensor false-positive;
  a real cooking session raises CO. None are constructed edge cases.
- Incarnations within a seed share the SAME trigger and SAME proposed_action.
  Only the situated variable differs. So a rule-only system necessarily gives
  the same output to all incarnations — the benchmark's whole point.
- Incarnation count follows the problem's natural structure (CO has 4 distinct
  physical causes → 4; pet timing has 3 meaningful clock relations → 3; child
  presence is binary → 2). Not padded, not forced to pairs.

---

## Instance counts (the body of data)

Each incarnation is generated across `seeds × salience` (and weather where
weather is causal). Target:
- seeds per incarnation: 30–50
- salience: 3 (clear / typical / subtle)
- => ~100–150 instances per incarnation

Totals (incarnations): CO=4, water=2, privacy=2, child=2, bath=2, nursery=2,
dinner=2, night_motion=3, pet=3, vacuum=2  =>  **24 incarnations**
across **10 seeds**, ~3000–3500 instances.

(The old "31 seeds / 23 runtime" count was counting incarnations as seeds.
The honest structure is 10 problems → 24 incarnations. Same coverage, clearer.)

---

## What moved out (criterion B: empty-house test)

Rule-interaction problems that persist in an empty house with neutral context
go to a SEPARATE benchmark, not here:
- timer_override, resource_contention, strobe_loop (the former L1, 6 seeds)
- fire_relock structural side (S2.9/10 structural half)

S2.9's situational half (fire makes "open window" wrong) is absorbed into the
CO_ventilation seed's fire incarnation — it's the same cause_mode reasoning.
