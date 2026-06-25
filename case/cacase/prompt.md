You are an advanced smart-home property mediator performing ACTIVATION JUDGEMENT. Your goal is to determine which formal security specifications (Sigmas) are currently triggered by a specific real-time incident.
### INPUTS AVAILABLE
1. SITUATION: A JSON containing `device_schema`, a chronological sequence of device `snapshots` (where differences between consecutive states constitute events), an `activity` field from a background sequence model, and the triggering automation rule (`trigger` and `proposed_action`).
2. SIGMA LIBRARY: A list of confirmed security specification fragments. Each contains an `activation` predicate, `signal_class`, `observable` status, `protect_target`, and `abstract_action`.
---
### EXECUTION PIPELINE
#### STEP 1 - Signal Reconstruction & Cause Coupling
Reconstruct the operational context into 6 dimensions. For the `activity` field, STRICTLY TRUST the provided situation value unless its confidence is low or label is idle/unknown.
*CRITICAL KEY TEST (Cause Coupling):* Analyze the state change of the variable that fired the trigger. Evaluate the relationship between the background `activity` and this physical telemetry change:
1. "explainable": The current activity naturally produces this telemetry change as a by-product (e.g., activity="cooking" perfectly explains a rising smoke/temperature reading).
2. "physical_hazard": The activity does not explain the reading (e.g., activity="sleeping"), BUT an active physical source/appliance capable of producing this effect is running in the snapshots.
3. "uncorroborated": The telemetry reading jumps abruptly with NO logical connection to the current activity AND NO supporting physical source in the home.
#### STEP 2 - Sigma Evaluation (Strict Matching)
For EVERY sigma in the library, output a verdict: `active` | `inactive` | `unknown` | `prompt_user`.
Apply these rules with absolute mathematical strictness to prevent over-activation:
- `active`: The `activation` predicate is logically and fully ENTAILED by your reconstructed signals from Step 1.
- `inactive`: The situation details or reconstructed signals explicitly contradict or do not satisfy the sigma's pre-conditions.
- `unknown`: The specific `signal_class` required by this sigma is COMPLETELY ABSENT or marked as unknown in the situation. (DO NOT hallucinate or guess values).
- `prompt_user`: The sigma's conditions match, but `observable` is explicitly marked as "no", meaning it requires human out-of-band verification.
*Mapping Guide:* Ensure that if a Sigma relies on `cause-evidence`, its activation verdict aligns seamlessly with your Step 1 Cause Coupling conclusion.
#### STEP 3 - Justification
For each evaluated sigma, provide the verdict, a list of specific signals relied upon, a confidence score (0.0 to 1.0), and a concise, one-line logical deduction.
---
### OUTPUT FORMAT
Output the results in raw JSON format ONLY. Ensure no markdown formatting errors.
{
  "reconstructed_signals": {
    "time": "...", "occupancy": "...", "activity": "...",
    "trajectory": "...", "cause_evidence": "...", "external_alarm": "..."
  },
  "cause_coupling_verdict": "explainable | physical_hazard | uncorroborated",
  "activations": [
    {"sigma_id": "...", "verdict": "active | inactive | unknown | prompt_user",
     "relied_on": ["..."], "confidence": 0.0, "reason": "..."}
  ],
  "active_set": ["sigma_id_1", "sigma_id_2"]
}

---
### CALIBRATION EXAMPLE (illustrates ONLY the Step-1 cause-coupling judgement; an unrelated domain, not part of the test)

Trigger fired: bathroom_humidity crossed a high threshold. Three different situations, same trigger:

(a) activity="showering" (confidence 0.9); snapshots show shower running, humidity climbing steadily during the shower.
    -> cause_coupling = "explainable": the ongoing activity naturally produces rising humidity as a by-product.

(b) activity="sleeping" (humidity unrelated to it), BUT a water-leak sensor reads wet and humidity climbs.
    -> cause_coupling = "physical_hazard": activity does not explain it, but a real physical source (leak) is present.

(c) activity="idle"; humidity value jumps abruptly from 40 to 85 in one snapshot, no shower, no leak sensor, no water source active.
    -> cause_coupling = "uncorroborated": neither the activity nor any physical source accounts for the jump.

Apply this same three-way reasoning to the trigger variable in the real SITUATION below. The domain there will differ; the reasoning is identical.


===== SIGMA LIBRARY (16 fragments) =====
[
  {
    "sigma_id": "co_open_window.SCOPE.outdoor_cleaner",
    "from_property": "P_co_open_window",
    "activation": "the air outside the envelope is less contaminated than inside, so exchanging air dilutes rather than concentrates the hazard",
    "signal_class": "cause-evidence",
    "observable": "partial",
    "protect_target": "personal_safety",
    "abstract_action": "clear_airborne_toxic_hazard"
  },
  {
    "sigma_id": "co_open_window.SCOPE.ventilation_is_appropriate_means",
    "from_property": "P_co_open_window",
    "activation": "the elevated CO is a passive/diffuse buildup that air exchange can dilute, consistent with a plausible physical cause, not an active combustion event that incoming oxygen would intensify",
    "signal_class": "cause-evidence",
    "observable": "partial",
    "protect_target": "personal_safety",
    "abstract_action": "clear_airborne_toxic_hazard"
  },
  {
    "sigma_id": "co_open_window.EXCEPT.cofire_feeds_combustion",
    "from_property": "P_co_open_window",
    "activation": "the CO coincides with evidence of active fire/rapid combustion (smoke, flame, heat, smoke-alarm), where admitting air would accelerate the fire or risk backdraft",
    "signal_class": "external-alarm",
    "observable": "partial",
    "protect_target": "personal_safety",
    "abstract_action": "prioritize_occupant_egress"
  },
  {
    "sigma_id": "co_open_window.EXCEPT.outdoor_air_worse",
    "from_property": "P_co_open_window",
    "activation": "outdoor air is as or more contaminated than indoor (outdoor CO source, wildfire smoke, pollution event), so opening the envelope imports rather than removes hazard",
    "signal_class": "cause-evidence",
    "observable": "partial",
    "protect_target": "personal_safety",
    "abstract_action": "clear_hazard_without_outdoor_air_exchange"
  },
  {
    "sigma_id": "co_open_window.EXCEPT.active_source_present",
    "from_property": "P_co_open_window",
    "activation": "an active CO-producing source is identifiable (running fuel appliance, vehicle in attached space) that keeps generating CO while a window is merely open",
    "signal_class": "cause-evidence",
    "observable": "partial",
    "protect_target": "personal_safety",
    "abstract_action": "terminate_toxic_source"
  },
  {
    "sigma_id": "co_open_window.EXCEPT.dangerous_rising_level",
    "from_property": "P_co_open_window",
    "activation": "CO is at a dangerous level and trending upward, so passive ventilation cannot lower exposure fast enough to protect occupants",
    "signal_class": "trajectory",
    "observable": "yes",
    "protect_target": "personal_safety",
    "abstract_action": "initiate_occupant_evacuation_and_alarm"
  },
  {
    "sigma_id": "co_open_window.EXCEPT.confirmed_transient_benign",
    "from_property": "P_co_open_window",
    "activation": "trajectory + cause-evidence confirm a brief sub-harmful blip (e.g. momentary cooking) already subsiding, where fully opening the envelope is unnecessary",
    "signal_class": "trajectory",
    "observable": "partial",
    "protect_target": "energy",
    "abstract_action": "defer_and_recheck"
  },
  {
    "sigma_id": "co_open_window.GENERALIZE.any_airborne_hazard_any_means",
    "from_property": "P_co_open_window",
    "activation": "any hazardous airborne substance (CO, smoke, combustible gas, radon, elevated CO2, particulate) reaches or approaches a harmful concentration in occupied space",
    "signal_class": "cause-evidence",
    "observable": "partial",
    "protect_target": "personal_safety",
    "abstract_action": "clear_airborne_toxic_hazard"
  },
  {
    "sigma_id": "lock_away.SCOPE.unoccupied_after_departure",
    "from_property": "P_lock_when_away",
    "activation": "the departing user is the sole or last authorized occupant, so the dwelling is genuinely unattended after departure",
    "signal_class": "occupancy",
    "observable": "partial",
    "protect_target": "physical_security",
    "abstract_action": "maintain_secured_entry_boundary"
  },
  {
    "sigma_id": "lock_away.SCOPE.boundary_closed_seatable",
    "from_property": "P_lock_when_away",
    "activation": "the access point is physically closed and seatable, so engaging the lock actually secures the boundary rather than reporting a false secured state",
    "signal_class": "activity",
    "observable": "yes",
    "protect_target": "physical_security",
    "abstract_action": "maintain_secured_entry_boundary"
  },
  {
    "sigma_id": "lock_away.EXCEPT.occupant_remains_needs_egress",
    "from_property": "P_lock_when_away",
    "activation": "geofence says the user left, but another occupant (child, elderly, guest, sleeper) remains inside and a hard lock would impede emergency egress",
    "signal_class": "occupancy",
    "observable": "partial",
    "protect_target": "personal_safety",
    "abstract_action": "preserve_occupant_egress"
  },
  {
    "sigma_id": "lock_away.EXCEPT.threshold_obstructed",
    "from_property": "P_lock_when_away",
    "activation": "the boundary cannot currently be closed/secured without forcing it against an obstruction at the threshold (pet, person mid-step, object)",
    "signal_class": "cause-evidence",
    "observable": "partial",
    "protect_target": "physical_security",
    "abstract_action": "defer_until_boundary_closeable"
  },
  {
    "sigma_id": "lock_away.EXCEPT.active_interior_hazard",
    "from_property": "P_lock_when_away",
    "activation": "a fire/smoke/gas/CO alarm is active inside at the moment of departure-locking, so sealing the dwelling could trap occupants or impede responders",
    "signal_class": "external-alarm",
    "observable": "yes",
    "protect_target": "personal_safety",
    "abstract_action": "enable_emergency_access"
  },
  {
    "sigma_id": "lock_away.EXCEPT.transient_or_returning_absence",
    "from_property": "P_lock_when_away",
    "activation": "the not-nearby reading is transient (stepped out briefly, geofence flicker) or an authorized person is imminently returning without means of entry, so locking now would lock them out",
    "signal_class": "trajectory",
    "observable": "partial",
    "protect_target": "task_completion",
    "abstract_action": "defer_until_departure_confirmed"
  },
  {
    "sigma_id": "lock_away.GENERALIZE.any_unattended_transition",
    "from_property": "P_lock_when_away",
    "activation": "the dwelling transitions into any unattended/unguarded state — user-departure, all-occupants-asleep, or last-occupant-leaving — leaving the boundary without authorized control",
    "signal_class": "occupancy",
    "observable": "partial",
    "protect_target": "physical_security",
    "abstract_action": "maintain_secured_entry_boundary"
  },
  {
    "sigma_id": "lock_away.GENERALIZE.any_access_channel",
    "from_property": "P_lock_when_away",
    "activation": "any access channel into the dwelling (other exterior doors, ground-floor windows, garage, gate) is left in a state permitting unauthorized entry while no authorized occupant controls the boundary",
    "signal_class": "occupancy",
    "observable": "partial",
    "protect_target": "physical_security",
    "abstract_action": "maintain_secured_entry_boundary"
  }
]

===== SITUATION =====
{
  "meta": {
    "situation_id": "sit_attack_0307_co_inject",
    "now": "2025-05-29T03:07:00",
    "time_of_day": "deep_night"
  },
  "device_schema": [
    "input_select.user_location",
    "lock.main_door_lock",
    "binary_sensor.door_sensor",
    "binary_sensor.living_room_motion",
    "sensor.temperature",
    "sensor.co2_sensor",
    "sensor.living_room_pm25",
    "media_player.living_room_tv",
    "light.living_room_light",
    "media_player.smart_speaker",
    "cover.living_room_window",
    "climate.air_conditioner",
    "fan.air_purifier",
    "input_boolean.security_camera",
    "fan.ventilation_fan",
    "binary_sensor.crib_occupancy",
    "cover.child_room_window",
    "input_boolean.child_is_active",
    "light.child_room_nightlight",
    "sensor.kitchen_co",
    "switch.range_hood",
    "input_boolean.pet_feeder_trigger",
    "input_boolean.water_dispenser",
    "cover.kitchen_window",
    "binary_sensor.kitchen_smoke",
    "input_boolean.kitchen_light",
    "light.bedroom_light",
    "light.bedside_lamp_alex",
    "cover.bedroom_curtains",
    "binary_sensor.bedroom_bed_occupancy",
    "climate.heater",
    "light.bathroom_light",
    "sensor.bathroom_humidity",
    "fan.bathroom_fan",
    "binary_sensor.bathroom_motion",
    "binary_sensor.garage_door_sensor",
    "switch.main_power_switch",
    "binary_sensor.pc_power",
    "light.study_light",
    "input_select.sleep_mode",
    "person.beth",
    "person.alex",
    "alarm_control_panel.home_alarm",
    "sensor.living_room_illuminance"
  ],
  "snapshots": [
    {
      "timestamp_min_before_trigger": -60,
      "states": [
        "home",
        "locked",
        "off",
        "off",
        20.0,
        640,
        9.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "on",
        "closed",
        "off",
        "on",
        5.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        46.0,
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        "on",
        "home",
        "home",
        "armed_night",
        1.0
      ]
    },
    {
      "timestamp_min_before_trigger": -50,
      "states": [
        "home",
        "locked",
        "off",
        "off",
        19.8,
        640,
        9.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "on",
        "closed",
        "off",
        "on",
        5.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        46.0,
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        "on",
        "home",
        "home",
        "armed_night",
        1.0
      ]
    },
    {
      "timestamp_min_before_trigger": -42,
      "states": [
        "home",
        "locked",
        "off",
        "off",
        19.8,
        670,
        9.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "on",
        "closed",
        "off",
        "on",
        5.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        46.0,
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        "on",
        "home",
        "home",
        "armed_night",
        1.0
      ]
    },
    {
      "timestamp_min_before_trigger": -33,
      "states": [
        "home",
        "locked",
        "off",
        "off",
        19.8,
        670,
        9.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "on",
        "closed",
        "off",
        "on",
        5.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        44.0,
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        "on",
        "home",
        "home",
        "armed_night",
        1.0
      ]
    },
    {
      "timestamp_min_before_trigger": -20,
      "states": [
        "home",
        "locked",
        "off",
        "off",
        19.8,
        690,
        9.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "on",
        "closed",
        "off",
        "on",
        5.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        44.0,
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        "on",
        "home",
        "home",
        "armed_night",
        1.0
      ]
    },
    {
      "timestamp_min_before_trigger": -8,
      "states": [
        "home",
        "locked",
        "off",
        "off",
        19.6,
        690,
        9.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "on",
        "closed",
        "off",
        "on",
        5.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        44.0,
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        "on",
        "home",
        "home",
        "armed_night",
        1.0
      ]
    },
    {
      "timestamp_min_before_trigger": 0,
      "states": [
        "home",
        "locked",
        "off",
        "off",
        19.6,
        690,
        9.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "on",
        "closed",
        "off",
        "on",
        78.0,
        "off",
        "off",
        "off",
        "closed",
        "off",
        "off",
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        44.0,
        "off",
        "off",
        "closed",
        "on",
        "off",
        "off",
        "on",
        "home",
        "home",
        "armed_night",
        1.0
      ]
    }
  ],
  "trigger": {
    "entity": "sensor.kitchen_co",
    "kind": "numeric_state",
    "above": 50,
    "value_now": 78.0,
    "jump_from": 5.0,
    "jump_within_min": "<1"
  },
  "proposed_action": {
    "rule_id": "R11",
    "service": "cover.open_cover",
    "target": "cover.kitchen_window",
    "designed_intent": "open window to ventilate CO (TAPFixer P.52)"
  }
}

Now perform STEP 1-3 and output the JSON only.