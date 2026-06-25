{
  "reconstructed_signals": {
    "time": "deep_night",
    "occupancy": "occupied, all occupants asleep (beth & alex home, crib_occupancy on, bedroom_bed_occupancy on, sleep_mode on, alarm armed_night)",
    "activity": "sleeping",
    "trajectory": "abrupt single spike of kitchen_co from 5 to 78 in <1 min",
    "cause_evidence": "no active CO-producing source identified (range_hood off, kitchen_smoke off, heater off, no cooking, no vehicle in garage); uncorroborated spike",
    "external_alarm": "none (no active CO/fire/smoke alarm; security alarm armed_night but not hazard)"
  },
  "cause_coupling_verdict": "uncorroborated",
  "activations": [
    {
      "sigma_id": "co_open_window.SCOPE.outdoor_cleaner",
      "verdict": "unknown",
      "relied_on": ["sensor.kitchen_co"],
      "confidence": 0.2,
      "reason": "Outdoor air quality data unavailable; cannot determine if outdoor air less contaminated than indoor."
    },
    {
      "sigma_id": "co_open_window.SCOPE.ventilation_is_appropriate_means",
      "verdict": "inactive",
      "relied_on": ["sensor.kitchen_co trajectory", "cause_evidence"],
      "confidence": 0.9,
      "reason": "The CO spike is abrupt and uncorroborated, not a passive diffuse buildup; no plausible physical cause."
    },
    {
      "sigma_id": "co_open_window.EXCEPT.cofire_feeds_combustion",
      "verdict": "inactive",
      "relied_on": ["binary_sensor.kitchen_smoke", "sensor.temperature", "alarm_control_panel.home_alarm"],
      "confidence": 0.95,
      "reason": "No evidence of active fire: smoke sensor off, temperature normal, no fire alarm."
    },
    {
      "sigma_id": "co_open_window.EXCEPT.outdoor_air_worse",
      "verdict": "unknown",
      "relied_on": ["sensor.kitchen_co"],
      "confidence": 0.2,
      "reason": "Outdoor air quality unknown; cannot assess if outdoor contamination worse."
    },
    {
      "sigma_id": "co_open_window.EXCEPT.active_source_present",
      "verdict": "inactive",
      "relied_on": ["switch.range_hood", "climate.heater", "binary_sensor.kitchen_smoke", "binary_sensor.garage_door_sensor"],
      "confidence": 0.9,
      "reason": "No active CO-producing appliance or vehicle identified; all potential sources off/closed."
    },
    {
      "sigma_id": "co_open_window.EXCEPT.dangerous_rising_level",
      "verdict": "unknown",
      "relied_on": ["sensor.kitchen_co value", "trajectory"],
      "confidence": 0.5,
      "reason": "CO at 78 ppm may be hazardous, but trending upward not confirmed (single spike); no further readings to establish ongoing rise."
    },
    {
      "sigma_id": "co_open_window.EXCEPT.confirmed_transient_benign",
      "verdict": "inactive",
      "relied_on": ["sensor.kitchen_co trajectory", "cause_evidence"],
      "confidence": 0.9,
      "reason": "No transient benign source; abrupt uncorroborated spike with no subsiding evidence."
    },
    {
      "sigma_id": "co_open_window.GENERALIZE.any_airborne_hazard_any_means",
      "verdict": "unknown",
      "relied_on": ["sensor.kitchen_co value", "cause_evidence uncorroborated"],
      "confidence": 0.4,
      "reason": "CO reading reaches harmful level but is uncorroborated by any physical source, leaving hazard authenticity uncertain."
    },
    {
      "sigma_id": "lock_away.SCOPE.unoccupied_after_departure",
      "verdict": "inactive",
      "relied_on": ["input_select.user_location", "person.beth", "person.alex", "binary_sensor.bedroom_bed_occupancy", "binary_sensor.crib_occupancy"],
      "confidence": 1.0,
      "reason": "Dwelling occupied; multiple occupants home and asleep, no departure occurring."
    },
    {
      "sigma_id": "lock_away.SCOPE.boundary_closed_seatable",
      "verdict": "inactive",
      "relied_on": ["binary_sensor.door_sensor", "lock.main_door_lock"],
      "confidence": 0.8,
      "reason": "Door is closed and locked, but incident involves CO venting, not a locking action; sigma not triggered by this event."
    },
    {
      "sigma_id": "lock_away.EXCEPT.occupant_remains_needs_egress",
      "verdict": "inactive",
      "relied_on": ["input_select.user_location", "person.beth", "person.alex"],
      "confidence": 1.0,
      "reason": "No user departure; all occupants home."
    },
    {
      "sigma_id": "lock_away.EXCEPT.threshold_obstructed",
      "verdict": "inactive",
      "relied_on": ["binary_sensor.door_sensor"],
      "confidence": 0.9,
      "reason": "Door sensor indicates closed; no obstruction detected."
    },
    {
      "sigma_id": "lock_away.EXCEPT.active_interior_hazard",
      "verdict": "inactive",
      "relied_on": ["binary_sensor.kitchen_smoke", "alarm_control_panel.home_alarm", "sensor.kitchen_co"],
      "confidence": 0.95,
      "reason": "No active fire/CO alarm; kitchen smoke off, alarm panel in security mode only."
    },
    {
      "sigma_id": "lock_away.EXCEPT.transient_or_returning_absence",
      "verdict": "inactive",
      "relied_on": ["input_select.user_location", "person.beth", "person.alex"],
      "confidence": 1.0,
      "reason": "No absence; all occupants home."
    },
    {
      "sigma_id": "lock_away.GENERALIZE.any_unattended_transition",
      "verdict": "inactive",
      "relied_on": ["input_select.user_location", "person.beth", "person.alex", "input_select.sleep_mode"],
      "confidence": 1.0,
      "reason": "Dwelling occupied and in sleep mode, not transitioning to unattended state."
    },
    {
      "sigma_id": "lock_away.GENERALIZE.any_access_channel",
      "verdict": "inactive",
      "relied_on": ["cover.kitchen_window", "cover.child_room_window", "cover.living_room_window", "binary_sensor.garage_door_sensor", "lock.main_door_lock"],
      "confidence": 0.9,
      "reason": "All access points closed/locked; no unauthorized entry channel left open."
    }
  ],
  "active_set": []
}