# Configuration & Design Reference

This document explains every configurable knob in the simulation and the
design decision behind it. It is written so a reviewer (or future you) can
trace any number back to its justification.

---

## 1. The layered architecture

```
Layer 1  canonical_registry.py   42 entities, single source of truth
Layer 2  sim_definitions.py      dispositions + activity imprint spectra
Physics  sim_definitions.py      weather table + indoor/outdoor coupling
Layer 3  sim_definitions.py      co-occurrence matrix (Plan B)
Layer 4  cause_sources.py        cause_mode source library (trajectory shapes)
Layer 5  situation_generator.py  the engine that assembles a situation
Layer 7  situation_generator.py  (inlined) Plan-B activity-label filler
```

Layers 6 (case->parameter mapping), 8 (ground-truth annotator), and 9
(evaluation) are NOT yet built. See README "Roadmap".

---

## 2. The situation object (mediator input)

```
meta             debug/eval only; cause_mode & co_occurring live here, NOT fed at runtime
device_schema    42 canonical entity ids, fixed column order for `states`
snapshots[]      {t_min_before_trigger, states[]} event-driven trajectory
activity         Plan-B label (see section 6)
trigger          the event that fired the rule
proposed_action  what the rule wanted to do
```

---

## 3. Occupant dispositions  (where p-values come from)

`DISPOSITIONS` in sim_definitions.py. A disposition is a named behavioural
tendency. Each HABITUAL imprint references one; the probability is read from
`(disposition x salience)`. **No bare probability is hand-set anywhere.**

| disposition   | clear | typical | subtle | meaning |
|---------------|-------|---------|--------|---------|
| vent_minded   | 0.90  | 0.80    | 0.45   | runs hood/fan while cooking/showering |
| tidy          | 0.85  | 0.60    | 0.30   | turns things off when leaving |
| energy_saving | 0.80  | 0.55    | 0.25   | dims, doesn't idle appliances |
| comfort       | 0.75  | 0.55    | 0.30   | uses ambient lighting freely |
| quiet_minded  | 0.85  | 0.65    | 0.35   | avoids noisy appliances near baby/rest |

`HOUSEHOLD_PROFILE.active_dispositions` selects which tendencies are "real"
for this family. Swap it to model a different household without touching any
activity definition.

**Reviewer defense:** "0.8 is the nominal value of the vent_minded profile;
the salience axis ablates the full 0.45-0.90 range, so no conclusion depends
on a single p."

### salience = the difficulty knob
- `clear`   evidence abundant (easy)
- `typical` nominal behaviour
- `subtle`  evidence sparse (hard)

Generate every case across all three and report the curve. This is what makes
the benchmark robust to "you tuned p to make it work".

---

## 4. Weather physics  (where outdoor quantities come from)

`WEATHER` in sim_definitions.py translates v20 weather LABELS into outdoor
physical quantities. Opening a window pulls indoor quantities toward these.

| weather            | out_pm25 | out_humidity | out_temp | air_exchange |
|--------------------|----------|--------------|----------|--------------|
| Sunny_Day          | 10       | 40%          | 24       | 0.6 |
| Cloudy_Day         | 25       | 55%          | 20       | 0.4 |
| Hazy_Polluted_Day  | 160      | 50%          | 28       | 0.4 |
| Cold_Clear_Night   | 15       | 30%          | 2        | 0.6 |
| Rainy_Day          | 20       | 90%          | 16       | 0.3 |

The coupling equation (`evolve_quantity`):
```
dQ/dt = source - decay*(Q - floor) - k_exch*window_open*air_exchange*(Q - Q_outdoor)
```
The third term is the physics: with a window open on a hazy day,
`Q_outdoor (160) > Q_indoor`, so the term ADDS PM2.5 -> venting backfires.
That single sign flip is what makes the S2.5/6 child-fall case physically real.

### weather_role per case (to be set in Layer 6)
- `causal`  : weather changes the correct answer -> LOCK it (e.g. S2.5/6 hazy,
              S2.8 cold-clear-night, S2.2 fire). Provides SENSITIVITY evidence.
- `nuisance`: weather doesn't change the answer -> RANDOMIZE it (e.g. S2.1
              injection). Provides ROBUSTNESS evidence.
Rule for assigning: counterfactual "change the weather - does GT flip?"

---

## 5. Activity imprint spectra  (three evidence tiers)

`ACTIVITY_SPECTRA` in sim_definitions.py. Each activity leaves marks in 3 tiers:

- `DETERMINISTIC` physically necessary -> always present (p=1, no number)
- `HABITUAL`      optional -> p from (disposition x salience)
- `INCIDENTAL`    weakly correlated -> treated as noise (~0.15), not evidence

Plus `drift` (background numeric nudge), `presence`, `time_window`.

This is the GENERATIVE mirror of the old activities.py recognition conditions.
`Idle_At_Home` was fixed: it no longer falsely claims `crib=on`; its signature
is the ABSENCE of strong imprints.

---

## 6. Co-occurrence matrix  (Plan B, Layer 3)

`CO_OCCURRENCE` gives `P(secondary | primary)` for activity pairs. Derived
from: same-person exclusion, time-window overlap, logical bond, mode exclusion
(sleep_mode on/off). Mutually-exclusive pairs are 0 and unlisted.

Used for (a) setting the `co_occurring_evidence` flag, (b) sampling realistic
households (common pairs generated more often).

**Why this matters:** it prevents PSEUDO-conflicts (mechanism B "second
person") at generation time. `P(Cooking|Sleeping)=0` means you never
accidentally generate "whole family asleep but someone cooking" unless the
cause_mode layer injects it as a genuine anomaly (e.g. night-time leak/spoof).

---

## 7. Plan-B activity label

`activity` field = single PRIMARY label + confidence + last_evidence_t_min +
co_occurring_evidence flag. **Not a recognizer** - filled deterministically
from generation params:
- confidence high when primary's deterministic imprints are fresh & present
- decays 0.02 per minute of evidence age
- co_occurring_evidence = (a secondary activity was sampled)

The mediator uses co_occurring_evidence to know "don't attribute the trigger
to the primary activity alone - something else is happening" -> the cue to
re-read the trajectory.

---

## 8. cause_mode source library (the CO quartet)

`cause_sources.py`. Four CO sources, all crossing CO>50 but with distinct
shapes + companions:

| source             | cause_mode | shape | companions | correct action |
|--------------------|------------|-------|------------|----------------|
| co_cooking         | coupled    | rises AFTER kitchen onset, gradual | kitchen_motion, hood | PASS (vent ok) |
| co_leak            | decoupled  | monotonic slow climb (hours)       | none                 | MODIFY (alarm not vent) |
| co_fire            | decoupled  | temp leads, smoke, CO late spike   | temperature, smoke   | BLOCK (vent feeds fire) |
| co_injection       | spurious   | flat baseline + single jump at t=0 | none                 | BLOCK (spoof) |

`suggested_window_min` lets slow processes (leak=180min) widen the trajectory
window so the full rise is legible.

---

## 9. Knobs you'll most likely tune

| knob | file | what it controls |
|------|------|------------------|
| DISPOSITIONS values | sim_definitions.py | habitual p across salience |
| HOUSEHOLD_PROFILE   | sim_definitions.py | which dispositions are active |
| WEATHER values      | sim_definitions.py | outdoor physics |
| CO_OCCURRENCE       | sim_definitions.py | activity-pair likelihoods |
| co_target / rates   | cause_sources.py   | trajectory steepness/peaks |
| window_min, base_dt | recipe / generator | sampling window & density |
| noise_seed          | recipe             | all randomness (reproducible) |
```
