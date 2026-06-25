下面是严格按 `property-refinement` 流程跑完的结果。先给出每个 move 的推导轨迹（便于核对），再给出规定的 JSON schema，最后用中文做收尾说明。

**Step 0 — Skeleton + intent lift**
- trigger：检测到 CO（一氧化碳）。
- action：把窗户打开（must_do）。
- intent：CO 是有毒气体，开窗是为了把积聚在室内呼吸空气中的毒气稀释/排出，避免居住者中毒。开窗只是手段。
- intent_lifted：`restore_breathable_air`（通风/稀释只是其中一种手段，窗户只是一个通道）。

**SCOPE**（作者默认、但没写进 trigger、也不在设备状态里的隐含场景）：① 室外空气比受污染的室内更干净，所以"对外开"才等于"稀释"；② 有人在场（或将要呼吸这片空气），清理它才保护到了人；③ 当前浓度低到"原地通风稀释"就足够，而不是已经到必须立刻撤离的程度。三条 SCOPE 都携带默认动作，标出默认有效的边界——而它们各自的反面正好是下面三条 EXCEPT。

**EXCEPT**（动作照写会背叛自身意图的情形，优先取 cause/trajectory/occupant-state/override）：① CO 其实来自室外（野火烟、并入车库的怠速引擎、邻居发电机、窗外废气积聚）→ 开窗反而引入更多毒气，动作反转为"封闭外壳"；② 浓度高/快速上升 → 原地稀释太慢，升级为"报警并提示撤离"；③ 家中无人且开窗会带来天气/入侵风险 → 改为"隔离排放源 + 远程报警"而非物理开窗。三条都 `static_rewriteable: false`。

**GENERALIZE**（按两条轴各长出一条 family-level 新候选，均 derived=true）：situation 轴把"CO"泛化为"任何让室内呼吸空气变得有害的气载危害"；object 轴把"窗户"泛化为"任何能恢复可呼吸空气的通道，包括切断源头"。

```json
{
  "property_id": "P_co_open_window",
  "source": "user-provided",
  "skeleton": {
    "trigger": "carbon monoxide (CO) is detected in indoor air",
    "action": "open the window",
    "action_modality": "must_do",
    "intent": "remove the accumulated toxic gas from the air occupants breathe so they are not poisoned; opening the window is only one means of dilution/ventilation",
    "intent_lifted": "restore_breathable_air — clear a hazardous airborne accumulation from occupied air; a window is one ventilation channel among many"
  },
  "fallback": "execute original action (open the window / ventilate) when no sigma activates",
  "sigmas": [
    {
      "sigma_id": "co_window.SCOPE.outdoor_air_cleaner",
      "move": "SCOPE",
      "label": "Outdoor air is cleaner than the contaminated indoor air (the dilution premise)",
      "activation": "the contaminant source is indoors and the outside air is cleaner than inside, so venting to outside actually lowers the indoor concentration",
      "protect_target": "personal_safety",
      "temporal_scope": "sustaining",
      "intent_served": "restore_breathable_air",
      "abstract_action": "restore_breathable_air",
      "observable": "partial",
      "signal_class": "cause-evidence",
      "static_rewriteable": true,
      "derived": false,
      "note": "Marks the boundary; its violation (source outside) is EXCEPT.intruding_outdoor_source."
    },
    {
      "sigma_id": "co_window.SCOPE.occupant_present",
      "move": "SCOPE",
      "label": "Someone is present to be protected by clearing the air",
      "activation": "at least one occupant is present (or will imminently breathe this air), so removing the toxic gas protects a real person",
      "protect_target": "personal_safety",
      "temporal_scope": "sustaining",
      "intent_served": "restore_breathable_air",
      "abstract_action": "restore_breathable_air",
      "observable": "yes",
      "signal_class": "occupancy",
      "static_rewriteable": true,
      "derived": false,
      "note": "Its violation (empty home) is EXCEPT.unoccupied_home."
    },
    {
      "sigma_id": "co_window.SCOPE.dilution_is_sufficient",
      "move": "SCOPE",
      "label": "Concentration is low enough that in-place dilution is an adequate response",
      "activation": "the detected level is low/stable enough that ventilating in place is a sufficient and timely response, rather than a level that demands immediate evacuation",
      "protect_target": "personal_safety",
      "temporal_scope": "sustaining",
      "intent_served": "restore_breathable_air",
      "abstract_action": "restore_breathable_air",
      "observable": "partial",
      "signal_class": "trajectory",
      "static_rewriteable": true,
      "derived": false,
      "note": "Its violation (high/rising level) is EXCEPT.dangerous_concentration."
    },
    {
      "sigma_id": "co_window.EXCEPT.intruding_outdoor_source",
      "move": "EXCEPT",
      "label": "Contaminant is coming from outside — opening admits more",
      "activation": "evidence that the CO (or hazardous gas) originates outdoors and is higher outside than inside — e.g. wildfire smoke, an idling engine in an attached garage venting toward the opening, a neighbor's generator, exhaust pooling under the window; opening the envelope would increase the indoor concentration",
      "protect_target": "personal_safety",
      "temporal_scope": "sustaining",
      "intent_served": "restore_breathable_air",
      "abstract_action": "seal_living_envelope",
      "observable": "partial",
      "signal_class": "cause-evidence",
      "static_rewriteable": false,
      "note": "Inverted action. Depends on source LOCATION/cause, unreadable from the bare detection instant."
    },
    {
      "sigma_id": "co_window.EXCEPT.dangerous_concentration",
      "move": "EXCEPT",
      "label": "Level is high and/or rising fast — dilution is too slow",
      "activation": "the concentration is high or climbing rapidly so that in-place ventilation cannot bring the air back to safe quickly enough; occupants are at acute risk",
      "protect_target": "personal_safety",
      "temporal_scope": "instant",
      "intent_served": "restore_breathable_air",
      "abstract_action": "alert_occupants_and_prompt_evacuation",
      "observable": "partial",
      "signal_class": "trajectory",
      "static_rewriteable": false,
      "note": "Escalation beyond the default. Depends on level + rate of rise (trajectory) plus occupant state."
    },
    {
      "sigma_id": "co_window.EXCEPT.unoccupied_home",
      "move": "EXCEPT",
      "label": "Home is empty — physically opening it serves no breather and exposes it",
      "activation": "no occupant is present, so the immediate breathe-safe benefit of opening is near-zero, while physically opening the envelope exposes the home to weather/intrusion; the gas should still be addressed",
      "protect_target": "physical_security",
      "temporal_scope": "sustaining",
      "intent_served": "restore_breathable_air",
      "abstract_action": "isolate_emission_source_and_alert",
      "observable": "yes",
      "signal_class": "occupancy",
      "static_rewriteable": false,
      "note": "personal_safety (rank 1) is dormant because no one is breathing the air now, so physical_security governs the choice; the chosen action still covers residual safety by isolating the source and alerting remotely. Depends on occupancy."
    },
    {
      "sigma_id": "co_window.GENERALIZE.any_airborne_hazard",
      "move": "GENERALIZE",
      "label": "Situation axis — any contaminant that makes occupied air unsafe, not only CO",
      "activation": "occupied indoor air becomes hazardous to breathe by ANY airborne contaminant or asphyxiant — not just CO, but a natural-gas/methane leak, smoke and combustion products from a fire, a refrigerant leak, radon accumulation, sewer gas / hydrogen sulfide, a dangerous CO2 buildup in a sealed or crowded room, solvent/VOC fumes, or oxygen displacement by a leaking inert gas (a nitrogen/argon/CO2 cylinder venting into a basement) — i.e. any case where breathing the air becomes unsafe, including the non-obvious ones the original CO trigger never named",
      "protect_target": "personal_safety",
      "temporal_scope": "sustaining",
      "intent_served": "restore_breathable_air",
      "abstract_action": "restore_breathable_air",
      "observable": "partial",
      "signal_class": "cause-evidence",
      "static_rewriteable": false,
      "derived": true,
      "note": "Some members (radon, CO2 buildup, O2 displacement, sewer gas) need sensors many homes lack → partial observability; mints new candidate properties serving the same lifted intent."
    },
    {
      "sigma_id": "co_window.GENERALIZE.any_ventilation_or_source_channel",
      "move": "GENERALIZE",
      "label": "Object axis — any means of restoring breathable air, beyond the window",
      "activation": "the means of restoring breathable air extends well beyond a window: any openable aperture (window, exterior door, skylight, roof/trickle vent); any powered ventilation (bathroom/kitchen exhaust fan, range hood, whole-house fan, HVAC fresh-air/purge mode); and the non-obvious non-opening channels — shutting a gas-supply valve, de-energizing a leaking combustion appliance, stopping a running engine, or running an air scrubber/purifier for particulates; whichever channel most lowers the contaminant in occupied air is the appropriate means",
      "protect_target": "personal_safety",
      "temporal_scope": "sustaining",
      "intent_served": "restore_breathable_air",
      "abstract_action": "restore_breathable_air",
      "observable": "partial",
      "signal_class": "cause-evidence",
      "static_rewriteable": false,
      "derived": true,
      "note": "'Appropriate means' explicitly includes source-isolation — a channel acting on a NEW object (the emitting appliance/valve), not an opening at all."
    }
  ],
  "user_checklist": [
    "SCOPE: When the source is indoors and outside air is cleaner, opening to ventilate is the right default. [Y/N]",
    "SCOPE: When someone is home, clearing the toxic air protects a real person, so ventilating is right. [Y/N]",
    "SCOPE: When the level is low/stable, ventilating in place (rather than evacuating) is a sufficient response. [Y/N]",
    "EXCEPT: When the gas is coming from OUTSIDE (wildfire, garage engine, neighbor's generator), keep the home sealed instead of opening. [Y/N]",
    "EXCEPT: When the level is high or rising fast, alert occupants and prompt evacuation rather than relying on ventilation alone. [Y/N]",
    "EXCEPT: When nobody is home, isolate the source and send a remote alert instead of physically opening an empty house. [Y/N]",
    "GENERALIZE: Apply the same 'make the air breathable again' response to other airborne hazards too — gas leak, smoke, radon, sewer gas, CO2 buildup, oxygen-displacing inert gases. [Y/N]",
    "GENERALIZE: Allow any channel to restore breathable air — other openings, exhaust/whole-house fans, HVAC purge, or shutting off the leaking source. [Y/N]",
    "Add your own: ____"
  ]
}
```

**收尾说明（中文）：**
- `intent_lifted` 是 `restore_breathable_air`——把"开窗"这个具体动作抽掉后剩下的设备无关目标：把积聚在居住者呼吸空气中的有害气体清除掉，让空气重新可安全呼吸；窗户只是众多通风通道之一。
- GENERALIZE 长出了两条 family-level sigma，分别落在两条新轴上。**situation 轴**（`any_airborne_hazard`）从"CO"扩到"任何让室内空气不可呼吸的气载危害"这个新场景类,activation 显式枚举了原 trigger 没提到的非显而易见成员:天然气/甲烷泄漏、火灾烟气、制冷剂泄漏、**氡气积聚**、**下水道气/硫化氢**、密闭房间里的 **CO₂ 超标**、**惰性气体（氮/氩/CO₂ 钢瓶）造成的缺氧**。
- **object 轴**（`any_ventilation_or_source_channel`）则落到"窗户"以外的新对象/通道上,activation 把这一类的成员列清:除了窗,还有门/天窗/通风口、排气扇/抽油烟机/全屋风扇/HVAC 新风净化模式,尤其是那个完全不是"开口"的非显而易见成员——**直接切断气源(关燃气阀、断电燃烧器具、熄掉怠速引擎)**,它作用在"排放源"这个全新对象上,而原属性的 action 永远到不了那里。

两条 GENERALIZE 都按构造标了 `derived: true` / `static_rewriteable: false`,且都进了 `user_checklist` 等你确认后再入库。


按 skill 的流程跑这条 property。

**Step 0 — 骨架 + intent lift**
- trigger:用户不在家 / 不在家附近(离开状态)
- action:门应当上锁(must_do)
- intent:在没有授权住户在场控制出入时,防止未授权进入住宅 —— 锁是手段,目的是住宅无人看管期间不让入侵路径处于可利用状态
- intent_lifted:`maintain_secured_perimeter_when_unattended`(前门的锁只是其中一种手段)

下面是完整输出:

```json
{
  "property_id": "P_lock_when_away",
  "source": "user-provided",
  "skeleton": {
    "trigger": "the authorized user is away from home / outside the near-home zone",
    "action": "the door is brought to a locked state",
    "action_modality": "must_do",
    "intent": "prevent unauthorized entry into the dwelling while no authorized occupant is present to control access",
    "intent_lifted": "maintain_secured_perimeter_when_unattended — keep every exploitable entry path closed whenever no authorized person is present to guard access; the front-door deadbolt is one means"
  },
  "fallback": "execute original action (bring the door to a locked state) when no sigma activates",
  "sigmas": [
    {
      "sigma_id": "lock_away.scope.sole_occupant",
      "move": "SCOPE",
      "label": "Default holds only when the leaving user is the sole authorized occupant and locking traps no one",
      "activation": "the departing user is the only authorized occupant and no other person or dependent being remains inside who would need the perimeter to stay openable; sealing the dwelling strands no one",
      "protect_target": "physical_security",
      "temporal_scope": "sustaining",
      "intent_served": "maintain_secured_perimeter_when_unattended",
      "abstract_action": "maintain_secured_perimeter_when_unattended",
      "observable": "partial",
      "signal_class": "occupancy",
      "static_rewriteable": false,
      "derived": false,
      "note": "SCOPE boundary: depends on full-occupancy knowledge that is NOT in the away/geofence trigger. Marks where the bare lock-on-away rule is validly the right thing."
    },
    {
      "sigma_id": "lock_away.scope.no_active_emergency",
      "move": "SCOPE",
      "label": "Default holds only while no in-progress emergency makes a sealed perimeter dangerous",
      "activation": "no fire/smoke/medical/intrusion-in-progress event is active that would make a sealed-and-hard-locked perimeter counterproductive; security is the correct priority at this moment",
      "protect_target": "physical_security",
      "temporal_scope": "sustaining",
      "intent_served": "maintain_secured_perimeter_when_unattended",
      "abstract_action": "maintain_secured_perimeter_when_unattended",
      "observable": "partial",
      "signal_class": "cause-evidence",
      "static_rewriteable": false,
      "derived": false,
      "note": "Implicit scene: 'secured' is the right goal only absent an emergency. Everything outside this boundary is where EXCEPT lives."
    },
    {
      "sigma_id": "lock_away.except.vulnerable_occupant_remains",
      "move": "EXCEPT",
      "label": "A vulnerable occupant remains inside who cannot operate the lock",
      "activation": "after the user leaves, a person or being who cannot reliably operate the lock remains inside (young child, frail/elderly person, disabled occupant, guest, confined pet); a hard-sealed perimeter could trap them in an egress emergency",
      "protect_target": "personal_safety",
      "temporal_scope": "sustaining",
      "intent_served": "preserve free egress for occupants (higher-priority than perimeter security)",
      "abstract_action": "secure_against_entry_while_preserving_egress",
      "observable": "partial",
      "signal_class": "occupancy",
      "static_rewriteable": false,
      "derived": false,
      "note": "Reduced/modified action: still deny entry, but never block exit. Depends on who else is present and their state, unreadable from the away trigger."
    },
    {
      "sigma_id": "lock_away.except.emergency_in_progress",
      "move": "EXCEPT",
      "label": "An emergency is in progress inside while the user is away",
      "activation": "while away, an interior emergency alarm fires (fire/smoke, CO, medical alarm) indicating responders or occupants need the perimeter openable",
      "protect_target": "personal_safety",
      "temporal_scope": "sustaining",
      "intent_served": "allow life-safety egress and responder entry (outranks perimeter security)",
      "abstract_action": "enable_emergency_responder_access",
      "observable": "yes",
      "signal_class": "external-alarm",
      "static_rewriteable": false,
      "derived": false,
      "note": "Override: locking betrays the higher intent here. Driven by alarm/cause-evidence, not by the away reading."
    },
    {
      "sigma_id": "lock_away.except.unsecurable_door",
      "move": "EXCEPT",
      "label": "The entry path is obstructed/ajar so a 'locked' state would be false or damaging",
      "activation": "the door is physically obstructed, jammed, or left ajar so that commanding a locked state would either fail silently (appearing secure while not), force against an obstruction, or damage the mechanism",
      "protect_target": "physical_security",
      "temporal_scope": "instant",
      "intent_served": "achieve genuine (not merely reported) perimeter security",
      "abstract_action": "report_unsecurable_perimeter",
      "observable": "partial",
      "signal_class": "cause-evidence",
      "static_rewriteable": false,
      "derived": false,
      "note": "Acting as written betrays its own intent — a false 'secured' is worse than an honest 'cannot secure'. Depends on the door's physical state, not the trigger instant."
    },
    {
      "sigma_id": "lock_away.except.brief_excursion_imminent_return",
      "move": "EXCEPT",
      "label": "Momentary step-out with imminent return",
      "activation": "the 'away / not nearby' reading is a brief excursion (curbside mail, trash, stepping just outside) with an imminent return and the resident may carry no means of re-entry; immediate locking risks stranding the authorized resident while serving negligible security",
      "protect_target": "task_completion",
      "temporal_scope": "instant",
      "intent_served": "avoid locking out the authorized resident",
      "abstract_action": "defer_and_recheck",
      "observable": "partial",
      "signal_class": "trajectory",
      "static_rewriteable": false,
      "derived": false,
      "note": "Depends on absence-duration / return-imminence trajectory, not the instantaneous geofence crossing."
    },
    {
      "sigma_id": "lock_away.except.already_secured",
      "move": "EXCEPT",
      "label": "Perimeter is already secured",
      "activation": "at the moment the away condition fires, the entry path is already in a verified locked/secured state, so re-actuation accomplishes nothing",
      "protect_target": "energy",
      "temporal_scope": "instant",
      "intent_served": "avoid redundant actuation",
      "abstract_action": "no_action",
      "observable": "yes",
      "signal_class": "activity",
      "static_rewriteable": true,
      "derived": false,
      "note": "Idempotency exception — readable from current lock state at the trigger instant, hence statically rewriteable."
    },
    {
      "sigma_id": "lock_away.generalize.any_unguarded_entry_path",
      "move": "GENERALIZE",
      "label": "Any exploitable entry path, whenever access is unguarded",
      "activation": "any entry/access path into the dwelling is left exploitable while no authorized occupant is actively guarding access. 'Entry/access path' covers not only the front door but any back/side door, the garage pedestrian door, the garage vehicle door, a sliding patio door, an accessible ground-floor or basement window, a person-sized pet door, an unlatched perimeter gate, AND non-physical channels such as an active temporary/guest access code, a one-time-share link still live, or a smart-access system left in a remotely-grantable/unauthenticated state. 'No authorized occupant guarding access' covers not only the resident being physically away / out of the geofence, but also the household having entered an extended-absence or vacation state, or all occupants being asleep and non-vigilant overnight",
      "protect_target": "physical_security",
      "temporal_scope": "sustaining",
      "intent_served": "maintain_secured_perimeter_when_unattended",
      "abstract_action": "maintain_secured_perimeter_when_unattended",
      "observable": "partial",
      "signal_class": "occupancy",
      "static_rewriteable": false,
      "derived": true,
      "note": "Family-level over BOTH axes (object = any access path incl. windows/garage/pet-door/digital channels; situation = any unguarded state incl. asleep/vacation). Speculative — must pass user checklist before entering any library."
    }
  ],
  "user_checklist": [
    "When you're the only one home and leaving, the system should just lock up as usual. [Y/N]",
    "While you're away and nothing's wrong, keeping the place sealed is the right default. [Y/N]",
    "If someone who can't work the lock is still inside (kid, elderly relative, guest, pet), the system should keep intruders out but never block their way out. [Y/N]",
    "If a fire/smoke/medical alarm goes off while you're away, the system should make the door openable for responders instead of staying hard-locked. [Y/N]",
    "If the door is jammed or propped open, the system should tell you it can't secure the door rather than pretend it's locked. [Y/N]",
    "If you just stepped outside for a second and are coming right back, the system should wait a moment before locking so it doesn't lock you out. [Y/N]",
    "If the door is already locked when you leave, the system should do nothing. [Y/N]",
    "DERIVED: Beyond the front door, the system should treat windows, the garage doors, sliding/patio doors, pet doors, gates, and any live guest codes / remote-access state as things to keep secured — and should also kick in when everyone's asleep or you're on extended vacation, not just when you've physically left. [Y/N]",
    "Add your own: ____"
  ]
}
```

简单说明:`intent_lifted` 是 `maintain_secured_perimeter_when_unattended` —— 把"锁门"抬升成"无人看管时让所有可被利用的入口都处于关闭状态",门锁只是其中一种手段。GENERALIZE 长出的那条 family-level sigma 同时在**情境轴**和**对象轴**上扩展:对象从"前门的锁"扩到"任何入口/出入通道",情境从"人离家/出了地理围栏"扩到"任何无人守卫出入的状态"。它的 activation 把原 trigger 没提到的非显而易见成员逐个枚举了进去 —— 对象侧:车库步行门和车库卷帘门、推拉露台门、可进入的一层/地下室窗户、人能钻过的宠物门、没插销的院门,以及**非物理通道**(仍然生效的临时访客密码、一次性共享链接、被留在"可远程授权/未认证"状态的智能门禁);情境侧:**全家熟睡的夜间**(有人在但不警觉)和**长期外出/度假模式**。这样下游判定器才不会把这条规则窄读回"只管前门 + 只在人物理离家时"那一个原始场景。