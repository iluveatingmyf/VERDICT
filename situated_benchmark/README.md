# Situated Runtime Mediation Benchmark — Simulation Suite

A generator for **situations**: snapshots of a smart home at the instant a
rule fires, used to test whether a runtime *mediator* can judge if the rule's
default action should execute, be modified, or be blocked — based on the full
situation rather than the rule's static condition.

The central claim this benchmark exists to prove:

> Given a rule firing whose surface signals are **identical** across two (or
> four) situations, the correct action differs — and only a mediator that
> reads the *situation* (trajectory shape, occupant state, cause) can tell
> them apart.

The flagship demonstration is the **CO quartet**: four situations that all
trigger `CO > 50 -> open window (R11)` with `value_now ≈ 70`, but whose
correct mediation is **PASS / MODIFY / BLOCK / BLOCK** (cooking / leak / fire
/ injection). A rule-only system outputs "open window" for all four; only a
situated mediator separates them.

---

## Install

No third-party dependencies. Python 3.8+.

```bash
cd situated_benchmark
python generate_demo.py        # writes the CO quartet to ./output/*.json
python simulation/batch_generator.py   # batch: seed x salience, varied activities
python tests/test_suite.py     # runs invariant tests (12 tests)
```

(With pytest installed: `python -m pytest tests/ -v`.)

---

## Layout

```
situated_benchmark/
├── simulation/
│   ├── canonical_registry.py    Layer 1: 42 entities, aliases, air domains
│   ├── sim_definitions.py       Layer 2/3 + physics: dispositions, weather,
│   │                            activity spectra, co-occurrence matrix
│   ├── cause_sources.py         Layer 4: CO quartet trajectory sources
│   └── situation_generator.py   Layer 5: the assembly engine (+ Plan-B label)
├── tests/
│   └── test_suite.py            invariant tests (the core claim is pinned here)
├── docs/
│   └── CONFIG.md                every knob explained, with reviewer defenses
├── generate_demo.py             entry point: emit the CO quartet as JSON
└── output/                      generated situation JSON files
```

See `docs/CONFIG.md` for the full design reference.

---

## How a situation is built (one sentence per layer)

1. **Registry** fixes the 42-entity vocabulary and the column order of `states`.
2. **Dispositions** give every habitual-imprint probability a provenance
   (profile × salience), so no `p` is hand-picked.
3. **Weather physics** makes opening a window actually pull indoor quantities
   toward weather-set outdoor values (so venting on a hazy day backfires).
4. **Activity spectra** stamp each activity's deterministic / habitual /
   incidental device imprints into the trajectory.
5. **Co-occurrence matrix** samples a realistic secondary activity, setting
   the `co_occurring_evidence` flag and preventing pseudo-conflicts.
6. **Cause sources** drive the trigger quantity with a distinct *shape* and
   *companions* per cause_mode.
7. **The engine** samples a low-frequency grid plus forced snapshots at causal
   events, assembling everything into one situation JSON.

---

## What Layer 6 added (cause→activity coupling)

- A **leak/injection can co-occur with ANY legal activity** — not a fixed
  empty house. "Legal" = passes three constraints: time-consistency,
  physical non-interference (a CO leak excludes Cooking so it can't forge CO
  evidence), presence-consistency. See `activity_coupling.py`.
- **coupled** causes LOCK the activity (cooking CO ⇒ Cooking); **decoupled/
  spurious** causes leave it FREE (sampled per seed); a case may PIN it for
  semantic reasons (injection-while-asleep).
- **Batch generation** across seed × salience: fixed seed list (reproducible),
  varied instances (distribution). A leak case meets Sleeping/Idle/Away/Night
  across its seeds. See `batch_generator.py`.
- **Extended cause sources**: CO, humidity (steam vs real leak), motion
  (sleepwalk vs intruder by spatial origin), timer, PM2.5, CO2.

## Design decisions already locked

- **Plan B** for multi-person: one primary activity label + `co_occurring`
  flag (not full per-person sequences). Avoids reviewer objection that a
  single label can't represent the family, without the cost of multi-track.
- **conflict mechanism A (label wrong) is out of scope** — the mediator does
  not second-guess the sequence model. Mechanism B (second person) is
  prevented by the co-occurrence matrix. Only mechanism C (independent cause:
  leak vs injection) is tested.
- **criterion B (the "empty-house test")** splits this benchmark from a second
  one: if a problem persists in an empty house with neutral context, it's a
  rule-interaction problem (-> separate benchmark); if it only appears given
  context, it stays here. This removed L1 (all) and S2.9/10 from the runtime set.
- **four flip-axes** organize the cases instead of L1/L2/L3 outcome layers:
  cause_mode, occupant-state, spatial-origin, timing.

---

## The catalog (seed_catalog.py)

10 seeds → 24 incarnations across 4 flip-axes, each a pure situation recipe
with a v20 ground-truth label (intervene/allow). All 24 generate valid,
distinct situations (`python simulation/generate_all.py`). See
`docs/SEED_DESIGN.md` for the problem→incarnations structure.

## Roadmap (not yet built)

| layer | component | status |
|-------|-----------|--------|
| 6 | cause→activity coupling + extended sources + batching | DONE |
| 6b | seed catalog: 10 seeds → 24 incarnations, all generate | DONE |
| 7 | activity-label filler | inlined in engine, to be extracted |
| 8 | ground-truth annotator (gt label → verdict DSL) | TODO (DSL deferred) |
| 9 | evaluation script (stratified report) | TODO |
| — | extend cause sources beyond CO (humidity, motion, timer, PM2.5) | TODO |
| — | second benchmark: rule-interaction static analysis | TODO |

Next step: build Layer 6 to map all 23 situational seeds onto the engine,
generating each case across the salience (and where applicable weather) axes.
```
