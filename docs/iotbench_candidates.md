# IoTBench Rule Candidate List — Week 1 Task 4

Corpus: IoTBench-test-suite  
Selection: **8 official** (SainT) + **4 malicious** (Soteria MalIoT) = **12 total**  
Scope: P1–P4 only. Cells marked **⚠ P5–P9** flag rules for Week 2 deeper analysis.

---

## Candidate Table

| # | Corpus | File | Rule Name | Triggers | Actions | Caps Read | Caps Written | Patterns |
|---|--------|------|-----------|----------|---------|-----------|--------------|----------|
| 1 | SainT-official | `brighten-my-path.groovy` | Brighten My Path | motion.active | switch.on | motion | switch | **P2, P3** |
| 2 | SainT-official | `darken-behind-me.groovy` | Darken Behind Me | motion.inactive | switch.off | motion | switch | **P2, P3** |
| 3 | SainT-official | `let-there-be-light.groovy` | Let There Be Light! | contact.open → switch.on; contact.closed → switch.off | switch.on / switch.off | contact | switch | **P2, P3** |
| 4 | SainT-official | `let-there-be-dark.groovy` | Let There Be Dark! | contact.open → switch.off; contact.closed → switch.on | switch.off / switch.on | contact | switch | **P2, P3** |
| 5 | SainT-official | `lock-it-when-i-leave.groovy` | Lock It When I Leave | presence.not_present | lock.lock + notification | presence | lock, notification | **P2, P3** |
| 6 | SainT-official | `unlock-it-when-i-arrive.groovy` | Unlock It When I Arrive | presence.present | lock.unlock + notification | presence | lock, notification | **P2, P3** |
| 7 | SainT-official | `smartblock-linker.groovy` | SmartBlock Linker | switch.on/off (from another switch) | light.setLevel / switch.on/off | switch | light, switch | **P1, P4** |
| 8 | SainT-official | `lights-off-with-no-motion-and-presence.groovy` | Lights Off with No Motion and Presence | motion.inactive + presence.not_present | switch.off | motion, presence | switch | **P2, P3** |
| 9 | Soteria-MalIoT | `ID1BrightenMyPath+.groovy` | Brighten My Path (malicious) | motion.active | switch.on(); **switch.off()** | motion | switch | **P2, P3** |
| 10 | Soteria-MalIoT | `ID2SecuritySystem+.groovy` | Security System (malicious) | presence.present → lock.unlock; presence.not_present → switch.off | lock.unlock / switch.off | presence | lock, switch | **P2, P3** |
| 11 | Soteria-MalIoT | `ID3SmokeAlarm+.groovy` | Smoke Alarm (malicious) | smoke.detected | alarm.strobe; fake alarm via HTTP + notification | smoke_detector | switch, notification | **P3**; ⚠ **P5** (runIn-based fake alarm 60 min later) |
| 12 | Soteria-MalIoT | `ID9DisableVacationMode+.groovy` | Disable Vacation Mode (malicious) | presence.not_present + switch.on | light.on/off (sunset/sunrise); notification | presence, switch | light, notification, switch | **P4**; ⚠ **P5, P8** (temporal sunset/sunrise handlers; infers vacation state) |

---

## Pattern Legend

| Pattern | Name | Definition |
|---------|------|------------|
| P1 | Causal chain | Rule A's action is the trigger event for Rule B (A writes device X; B subscribes to X state change) |
| P2 | Conflicting writes | Two rules issue opposing commands to the same device/capability (e.g., `.on()` vs `.off()` on the same switch) |
| P3 | Shared trigger | Two or more rules subscribe to the same device/event, creating a fan-out that may produce unexpected joint effects |
| P4 | State sharing | Rule A writes a device; Rule B reads that device's state to decide its own action (shared mutable state) |
| ⚠ P5 | Temporal dependency | Rule behaviour depends on absolute time or a scheduled delay (`runIn`, sunrise/sunset); requires temporal analysis (Week 2) |
| ⚠ P8 | Inference dependency | Rule implicitly infers environment state (e.g., "vacation mode") from a combination of device states; requires semantic analysis (Week 2) |

---

## Interaction Pairs (P1–P4)

The table below shows which candidate pairs exhibit a pattern together, assuming they share physical devices.

| Pattern | Rule A | Rule B | Notes |
|---------|--------|--------|-------|
| P2 | #1 BrightenMyPath | #2 DarkenBehindMe | Same motion sensor, same switch — one turns on, other turns off |
| P2 | #3 LetThereBeLight | #4 LetThereBeDark | Same contact sensor, same switch — inverted open/close logic |
| P2 | #5 LockWhenLeave | #6 UnlockWhenArrive | Same presence sensor, same lock — lock vs unlock on departure |
| P2 | #8 LightsOffNoMotion | #1 BrightenMyPath | Same motion sensor, same switch — #1 turns on, #8 turns off on inactive |
| P2 | #9 MalBrightenMyPath | #1 BrightenMyPath | Same motion event, same switch — legitimate rule turns on; malicious immediately turns off |
| P2 | #10 MalSecuritySystem | #5 LockWhenLeave | Same presence, same lock — #5 locks on departure; #10 unlocks on arrival then disables security |
| P3 | #1 BrightenMyPath | #2 DarkenBehindMe | Both subscribe to `motion1` (different events: active vs inactive) |
| P3 | #1 BrightenMyPath | #8 LightsOffNoMotion | Both subscribe to motion sensor |
| P3 | #3 LetThereBeLight | #4 LetThereBeDark | Both subscribe to `contact1` |
| P3 | #5 LockWhenLeave | #6 UnlockWhenArrive | Both subscribe to `presence1` |
| P3 | #5 LockWhenLeave | #10 MalSecuritySystem | Both subscribe to presence sensor |
| P3 | #11 MalSmokeAlarm | (any smoke rule) | smoke.detected is a shared safety-critical event |
| P1 | #1 BrightenMyPath | #7 SmartBlockLinker | #1 writes switch.on → #7 subscribed to switch state change fires (causal chain) |
| P4 | #7 SmartBlockLinker | #1 BrightenMyPath | #7 reads switch state that #1 writes; bidirectional coupling creates loop risk |
| P4 | #12 MalVacationMode | any switch-writing rule | #12 reads switch state to enter/exit vacation mode; external switch write changes mode silently |

---

## Drop Log (rules evaluated but excluded)

| File | Reason |
|------|--------|
| `ID13RunTimeLogicRequired+.groovy` | Parser drop: no parseable subscribe() or device command (runtime dynamic dispatch only) |
| `ID4PowerAllowance+.groovy` | Excluded from 12: P4 pattern redundant with SmartBlock Linker; no new pattern demonstrated |
| `ID5DynamicMethodInvocationAlarm+.groovy` | Excluded: dynamic method invocation (`v."$state.command"()`) — requires Week 2 semantic analysis |
| `ID12RemoteCommand+.groovy` | Excluded: C2-based remote command execution — no static P1–P4 pattern extractable |
| `enhanced-auto-lock-door.groovy` | Excluded from 12: temporal runIn logic (flag P5); P2/P3 covered by rules #5/#6 |

---

## Coverage Summary

| Pattern | Count in Candidate Set | Example Pair |
|---------|-----------------------|--------------|
| P1 | 1 | #1 → #7 |
| P2 | 6 pairs | #1 ↔ #2, #3 ↔ #4, #5 ↔ #6, #8 ↔ #1, #9 ↔ #1, #10 ↔ #5 |
| P3 | 6 pairs | #1/#2, #3/#4, #5/#6, #1/#8, #5/#10, #11/(smoke rules) |
| P4 | 2 | #7 (switch→light), #12 (switch read) |
| P5 flag | 2 | #11, #12 |
| P8 flag | 1 | #12 |
