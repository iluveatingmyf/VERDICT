# SmartAppZoo (GitHub Third-Party) Rule Candidate List — Week 1 Task 5

Corpus: `datasets/SmartAppZoo/Github Third-Party/`  
Parsed: 776 multi-capability rules out of 2,874 total Groovy files  
Selection: **4 candidates** emphasising interaction patterns not already covered by the 12 IoTBench rules  
Scope: P1–P4. Cells marked **⚠ P5–P9** flag rules for Week 2 deeper analysis.

---

## Candidate Table

| # | File | Rule Name | Triggers | Actions | Caps Read | Caps Written | Patterns |
|---|------|-----------|----------|---------|-----------|--------------|----------|
| 13 | `lights-when-door-unlocks[astrowings@SmartThings].groovy` | Lights When Door Unlocks | lock.unlock | switch.on (then switch.off after N min via runIn) | lock | switch | **P1**; ⚠ **P5** (timed off via runIn) |
| 14 | `Link-Switch-And-Lock[aderusha@SmartThings].groovy` | Link Switch and Lock | switch.on/off ↔ lock.lock/unlock (bidirectional) | lock.lock/unlock, switch.on/off | lock, switch | lock, switch | **P1, P4** (feedback loop risk) |
| 15 | `3-speed-ceiling-fan-thermostat-bkp[Welasco@SmartthingsFanControlHubitat].groovy` | 3 Speed Ceiling Fan Thermostat | temperature.measured, motion.active, motion.inactive, presence.present | light.setLevel (fan speed), switch.on | motion, presence, temperature | light, switch | **P3, P4** |
| 16 | `smart-come-and-go[ianisms@st-ianisms].groovy` | Smart Come and Go | presence.present/not_present, contact.open, lock.lock, motion.active | lock.unlock, switch.off/on, notification | contact, lock, motion, presence | lock, notification, switch | **P2, P3, P4** |

---

## Pattern Rationale

### Rule 13 — Lights When Door Unlocks (P1, ⚠P5)

**Why selected**: Cleanest possible P1 (causal chain) example from the third-party corpus. The rule subscribes exclusively to `lock.unlocked` — meaning it can only fire if another rule (or user action) unlocks the door first. Combined with `unlock-it-when-i-arrive` (IoTBench rule #6), this creates:

```
presence.present → lock.unlock  (Rule #6)
              └→ lock.unlocked event → switch.on  (Rule #13)   ← P1 causal chain
```

The `leaveOn` timer (`runIn(leaveOn * 60, turnOff)`) adds a time-bounded light-off action — flagged **P5** for Week 2.

**New pattern coverage**: P1 was present in the IoTBench set only via SmartBlock Linker (switch→light). This rule adds a second, cleaner P1 instance via lock→switch, a safety-relevant capability pair.

---

### Rule 14 — Link Switch and Lock (P1, P4 — feedback loop)

**Why selected**: Symmetric bidirectional coupling between a switch and a lock. The app subscribes to both `switch.on/off` events AND `lock.lock/unlock` events and propagates state in both directions:

```
switch.on  → lock.unlock   (P1 causal chain)
lock.unlock → switch.on   (P1 causal chain, reverse direction)
```

This creates a **feedback loop** (P4 state sharing + P1 cycle): if any external rule changes the switch, it changes the lock, which changes the switch again. The app includes loop-guard logic (`updateSwitchState` / `updateBlockState` flags), but the loop risk is real under concurrent rule execution.

**New pattern coverage**: First example in the candidate set of a **bidirectional P1 loop**, which is a distinct risk from the unidirectional IoTBench P1 chain.

---

### Rule 15 — 3 Speed Ceiling Fan Thermostat (P3, P4)

**Why selected**: Multi-sensor trigger fan speed control. Subscribes to temperature, motion (active + inactive), and presence — a superset of sensors used by IoTBench motion rules (#1, #2, #8). This creates rich P3 fan-out:

```
motion.active →  (Rule #1 BrightenMyPath turns on switch)
              →  (Rule #15 CeilingFan adjusts fan speed)   ← P3 shared trigger
```

Also exhibits P4: temperature sensor reading drives `light.setLevel(fanLevel)` output — the temperature state is continuously read to determine a continuous actuator command, a control-loop pattern distinct from the binary on/off patterns in the IoTBench set.

**New pattern coverage**: First temperature-driven actuator control rule. Introduces `temperature` → `light` (setLevel) as a new capability write path.

---

### Rule 16 — Smart Come and Go (P2, P3, P4)

**Why selected**: Richest multi-pattern rule in the SmartAppZoo corpus. Five distinct triggers (presence present/not_present, contact open, lock state, motion) drive four distinct action capabilities. Key patterns:

- **P2**: presence.present → `lock.unlock` conflicts directly with IoTBench rule #5 (`lock-it-when-i-leave`) which locks on `presence.not_present` on the same sensor. Two rules writing opposing lock states based on complementary presence events.
- **P3**: Shares presence, contact, lock, and motion triggers with IoTBench rules #5, #6, #8 and with Rule #13/#14 above.
- **P4**: Reads `lock.lock` event (trigger) and writes `lock.unlock` (action) — the same device is both read and written, with the rule deciding unlock based on observed lock state.

**New pattern coverage**: First rule combining P2 + P3 + P4 simultaneously, demonstrating interaction complexity that scales beyond pairwise analysis.

---

## Interaction Pairs with IoTBench Candidates

| Pattern | Rule A | Rule B | Notes |
|---------|--------|--------|-------|
| P1 | #6 UnlockWhenArrive (IoTBench) | #13 LightsWhenDoorUnlocks | Arrival unlocks door → lights turn on |
| P1 | #14 LinkSwitchAndLock | #14 LinkSwitchAndLock (self) | Bidirectional loop: switch↔lock state propagation |
| P1 | any switch-writing rule | #14 LinkSwitchAndLock | Switch write propagates to lock, potentially re-triggering other rules |
| P2 | #5 LockWhenLeave (IoTBench) | #16 SmartComeAndGo | Shared presence sensor; #5 locks on departure, #16 unlocks on arrival |
| P2 | #6 UnlockWhenArrive (IoTBench) | #16 SmartComeAndGo | Both unlock on presence.present — redundant but consistent |
| P3 | #1 BrightenMyPath (IoTBench) | #15 CeilingFanThermostat | Both subscribe to motion.active on same sensor |
| P3 | #8 LightsOffNoMotion (IoTBench) | #15 CeilingFanThermostat | Both subscribe to motion.inactive |
| P3 | #5/#6 (IoTBench) | #16 SmartComeAndGo | All three subscribe to presence sensor |
| P4 | #13 LightsWhenDoorUnlocks | #6 UnlockWhenArrive (IoTBench) | Lock state written by #6 is the trigger state read by #13 |
| P4 | #14 LinkSwitchAndLock | any switch-writing rule | Switch state written externally is immediately read by #14 to update lock |
| P4 | #16 SmartComeAndGo | #5/#6 (IoTBench) | #16 reads lock.lock event; #5/#6 write lock state |

---

## Drop Log (SmartAppZoo rules evaluated but excluded)

| File | Reason |
|------|--------|
| `user-lock-manager[josephbolus@SmartThingsPersonal].groovy` | Only trigger: lock.lock → notification; no new patterns beyond IoTBench |
| `set-mode-when-lock-status-changes[PurelyNicole@SmartThingsApps].groovy` | Parser drop: subscribe to lock but no device command actions extracted |
| `TemperatureBasedDeviceControl[jschollenberger@SmartThings].groovy` | Parser drop: no subscribe() triggers found (uses scheduled polling only) |
| `ScheduledMotionDimmer[bkeifer@smartthings].groovy` | Parser drop: subscribe to motion but no device command actions (dynamic dimmer logic) |
| `AI[sbdobrescu@SmartThings].groovy` | Excluded: hub-level API aggregator (9 triggers, 3 caps written) — too broad to model as a single rule; P5–P9 scope |
| `ActiON4SmartApp[SANdood@ActiON-Dashboard].groovy` | Excluded: dashboard/API bridge, not an automation rule |

---

## Updated Coverage Summary (IoTBench + SmartAppZoo, rules #1–#16)

| Pattern | Count | Key Examples |
|---------|-------|--------------|
| P1 | 3 | #1→#7 (switch chain), #6→#13 (lock→switch), #14↔#14 (bidirectional loop) |
| P2 | 7+ pairs | #1↔#2, #3↔#4, #5↔#6, #9↔#1, #10↔#5, #5↔#16 |
| P3 | 8+ pairs | All motion rules share trigger; all presence rules share trigger |
| P4 | 4 | #7 (switch→light), #12 (vacation switch), #14 (bidirectional), #16 (lock r/w) |
| P5 flag | 3 | #11 (fake alarm), #12 (sunset/sunrise), #13 (timed light off) |
| P8 flag | 1 | #12 (vacation state inference) |
