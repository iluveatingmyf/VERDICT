# filename: simulation/canonical_registry.py
# CANONICAL ENTITY REGISTRY  —  frozen from benchmark_data.py v20.0
# ----------------------------------------------------------------------
# This is the single source of truth for entity IDs. activities, event
# scripts, rules, and the situation generator MUST all reference names
# from here. Where v20 was internally inconsistent, the v20 benchmark
# spelling wins (it is what the seeds actually use).
#
# Each entry: canonical_id -> {domain, type, values/range, room, aliases}
#   aliases = other spellings seen in older files (activities.py, scaffold,
#             handoff doc) that map onto this canonical id. Used by a
#             normalization pass so legacy definitions don't silently break.
# ----------------------------------------------------------------------

REGISTRY = {

    # ================= KITCHEN =================
    "sensor.kitchen_co": {
        "domain": "sensor", "type": "numeric", "unit": "ppm",
        "baseline": 5.0, "room": "kitchen",
        "aliases": ["sensor.co_sensor"],
    },
    "binary_sensor.kitchen_smoke": {
        "domain": "binary_sensor", "type": "binary", "room": "kitchen",
        "aliases": ["binary_sensor.kitchen_smoke_detector"],
    },
    "oven.kitchen_oven": {
        "domain": "oven", "type": "binary", "room": "kitchen",
        "aliases": [],
    },
    "switch.range_hood": {
        "domain": "switch", "type": "binary", "room": "kitchen",
        "aliases": [],
    },
    "binary_sensor.kitchen_motion": {
        "domain": "binary_sensor", "type": "binary", "room": "kitchen",
        # Added: kitchen is semi-open but cooking ALWAYS produces movement at
        # the counter/stove. This is the hardest deterministic cooking signal.
        # One of the 4 motion sensors (floor-plan icon 5) covers the kitchen.
        "aliases": [],
    },
    "light.kitchen_light": {
        "domain": "light", "type": "binary", "room": "kitchen",
        # floor-plan icon 30
        "aliases": [],
    },
    "cover.kitchen_window": {
        "domain": "cover", "type": "open_closed", "room": "kitchen",
        # NOTE: R11 (CO ventilation) action target. v20 CO seeds trigger on
        # CO but don't spell the cover; automations.yaml target is
        # sim_kitchen_window_switch. NEEDS CONFIRM (see open question Q1).
        "aliases": ["input_boolean.sim_kitchen_window_switch"],
    },

    # ================= LIVING ROOM / NURSERY =================
    "sensor.living_room_co2": {
        "domain": "sensor", "type": "numeric", "unit": "ppm",
        "baseline": 450.0, "room": "living_room",
        "aliases": ["sensor.co2_sensor"],
    },
    "sensor.living_room_pm25": {
        "domain": "sensor", "type": "numeric", "unit": "ugm3",
        "baseline": 10.0, "room": "living_room",
        "aliases": ["sensor.living_room_pm25"],
    },
    "sensor.living_room_temperature": {
        "domain": "sensor", "type": "numeric", "unit": "C",
        "baseline": 21.0, "room": "living_room",
        "aliases": ["sensor.temperature"],
    },
    "sensor.living_room_illuminance": {
        "domain": "sensor", "type": "numeric", "unit": "lux",
        "baseline": 100.0, "room": "living_room",
        "aliases": [],
    },
    "binary_sensor.living_room_motion": {
        "domain": "binary_sensor", "type": "binary", "room": "living_room",
        "aliases": ["binary_sensor.motion_sensor_living_room"],
    },
    "light.living_room_light": {
        "domain": "light", "type": "binary", "room": "living_room",
        "aliases": ["light.main_light", "input_boolean.sim_living_room_light_switch"],
    },
    "media_player.living_room_tv": {
        "domain": "media_player", "type": "media_state", "room": "living_room",
        "aliases": ["media_player.tv"],
    },
    "cover.living_room_window": {
        "domain": "cover", "type": "open_closed", "room": "living_room",
        # used by intruder/sleepwalk seed (S2.13/14) as boundary breach signal
        "aliases": ["input_boolean.sim_living_room_window_switch"],
    },
    "fan.ventilation_fan": {
        "domain": "fan", "type": "binary_timer", "room": "living_room",
        # R24 CO2 ventilation fan; supports timer_remaining in preconditions
        "aliases": ["input_boolean.sim_ventilation_fan_is_on"],
    },
    "vacuum.robot_vacuum": {
        "domain": "vacuum", "type": "vacuum_state", "room": "living_room",
        "aliases": ["input_boolean.sim_vacuum"],
    },
    "switch.pet_feeder": {
        "domain": "switch", "type": "binary", "room": "living_room",
        "aliases": ["input_boolean.sim_pet_feeder_switch"],
    },
    "binary_sensor.crib_occupancy": {
        "domain": "binary_sensor", "type": "binary", "room": "nursery",
        "aliases": ["binary_sensor.crib_sensor"],
    },
    "input_boolean.child_is_active": {
        "domain": "input_boolean", "type": "binary", "room": "nursery",
        "aliases": [],
    },
    "light.child_nightlight": {
        "domain": "light", "type": "binary", "room": "nursery",
        "aliases": [],
    },
    "cover.child_room_window": {
        "domain": "cover", "type": "open_closed", "room": "living_room",
        # PHYSICAL: floor plan has NO separate child room. This is the
        # living-room window adjacent to the nursery zone. R13 (PM2.5
        # ventilation) target. The fall hazard in S2.5/6 is real because
        # this window opens right next to where the child plays. v20 id kept.
        "aliases": [],
    },

    # ================= BATHROOM =================
    "sensor.bathroom_humidity": {
        "domain": "sensor", "type": "numeric", "unit": "pct",
        "baseline": 45.0, "room": "bathroom",
        "aliases": [],
    },
    "binary_sensor.bathroom_motion": {
        "domain": "binary_sensor", "type": "binary", "room": "bathroom",
        "aliases": [],
    },
    "light.bathroom_light": {
        "domain": "light", "type": "binary", "room": "bathroom",
        "aliases": ["input_boolean.sim_bathroom_light"],
    },
    "fan.bathroom_fan": {
        "domain": "fan", "type": "binary", "room": "bathroom",
        # R1 humidity fan
        "aliases": ["input_boolean.sim_bathroom_fan_is_on"],
    },
    "binary_sensor.laundry_room_water_leak": {
        "domain": "binary_sensor", "type": "binary", "room": "bathroom",
        # PHYSICAL: floor plan has NO laundry room. Leak sensor (icon 13) is
        # in the BATHROOM. v20 id kept as-is so seeds don't break. The steam
        # false-positive in S2.8 is valid: shower steam reaches this sensor
        # in the same room.
        "aliases": ["binary_sensor.water_leak_sensor"],
    },

    # ================= BEDROOM (Alex) =================
    "binary_sensor.master_bed_occupancy": {
        "domain": "binary_sensor", "type": "binary", "room": "bedroom",
        "aliases": ["binary_sensor.bed_sensor"],
    },
    "light.study_lamp": {
        "domain": "light", "type": "binary", "room": "bedroom",
        "aliases": [],
    },
    "switch.pc_power": {
        "domain": "switch", "type": "binary", "room": "bedroom",
        "aliases": [],
    },
    "binary_sensor.bedroom_motion": {
        "domain": "binary_sensor", "type": "binary", "room": "bedroom",
        "aliases": ["binary_sensor.motion_sensor_bedroom"],
    },

    # ================= DOORS / GLOBAL SECURITY =================
    "lock.front_door": {
        "domain": "lock", "type": "lock_state", "room": "global",
        "aliases": ["input_boolean.sim_main_door_is_locked",
                    "input_boolean.sim_main_door_lock"],
    },
    "binary_sensor.front_door_contact": {
        "domain": "binary_sensor", "type": "binary", "room": "global",
        "aliases": ["binary_sensor.door_contact", "binary_sensor.door_sensor"],
    },
    "alarm_control_panel.main_alarm": {
        "domain": "alarm_control_panel", "type": "alarm_state", "room": "global",
        # states: disarmed, armed_home, armed_away, armed_night, triggered
        # (armed_home added per floor-plan review; armed_night -> S2.13/14,
        #  armed_away -> S2.15/16)
        "states": ["disarmed", "armed_home", "armed_away", "armed_night", "triggered"],
        "aliases": ["alarm_control_panel.home_alarm"],
    },
    "input_boolean.security_camera": {
        "domain": "input_boolean", "type": "binary", "room": "global",
        "aliases": ["input_boolean.sim_security_camera_is_on",
                    "input_boolean.sim_security_camera"],
    },
    "switch.main_power": {
        "domain": "switch", "type": "binary", "room": "global",
        "aliases": ["input_boolean.sim_main_power_switch"],
    },
    "climate.main_hvac": {
        "domain": "climate", "type": "hvac_mode", "room": "global",
        # modes seen: cool, off (also heat in v-drivers)
        "aliases": ["input_boolean.sim_hvac"],
    },

    # ================= LOGICAL / PRESENCE =================
    "group.family": {
        "domain": "group", "type": "home_state", "room": "logical",
        # home / not_home
        "aliases": [],
    },
    "person.alex": {
        "domain": "person", "type": "home_state", "room": "logical",
        "aliases": [],
    },
    "person.beth": {
        "domain": "person", "type": "home_state", "room": "logical",
        "aliases": [],
    },
    "input_select.sleep_mode": {
        "domain": "input_select", "type": "on_off_select", "room": "logical",
        "aliases": [],
    },
    "input_select.user_location": {
        "domain": "input_select", "type": "location_select", "room": "logical",
        # home / away
        "aliases": [],
    },
}


# ---- alias -> canonical lookup, for normalizing legacy definitions ----
ALIAS_MAP = {}
for canon, meta in REGISTRY.items():
    for a in meta.get("aliases", []):
        ALIAS_MAP[a] = canon

def canonicalize(entity_id: str) -> str:
    """Map any legacy/alias entity id to its canonical form."""
    if entity_id in REGISTRY:
        return entity_id
    return ALIAS_MAP.get(entity_id, entity_id)  # unknown passes through


if __name__ == "__main__":
    print(f"Canonical entities: {len(REGISTRY)}")
    print(f"Alias mappings:     {len(ALIAS_MAP)}")
    # group by room for review
    from collections import defaultdict
    by_room = defaultdict(list)
    for cid, m in REGISTRY.items():
        by_room[m["room"]].append(cid)
    for room in ["kitchen", "living_room", "nursery", "bathroom",
                 "bedroom", "global", "logical"]:
        print(f"\n[{room}]")
        for cid in by_room[room]:
            t = REGISTRY[cid]["type"]
            al = REGISTRY[cid]["aliases"]
            alias_note = f"   <- {', '.join(al)}" if al else ""
            print(f"  {cid:<42} {t}{alias_note}")


# ---- air domain metadata (from floor plan) ----
# Shared-air zones determine how numeric quantities (CO, CO2, PM2.5, humidity)
# diffuse. Nursery shares living_room air; kitchen is adjacent to living.
AIR_DOMAIN = {
    "sensor.living_room_co2": "living_zone",
    "sensor.living_room_pm25": "living_zone",
    "sensor.living_room_temperature": "living_zone",
    "binary_sensor.crib_occupancy": "living_zone",
    "light.child_nightlight": "living_zone",
    "input_boolean.child_is_active": "living_zone",
    "fan.ventilation_fan": "living_zone",
    "cover.child_room_window": "living_zone",
    "cover.living_room_window": "living_zone",
    "sensor.kitchen_co": "kitchen_zone",
    "binary_sensor.kitchen_smoke": "kitchen_zone",
    "cover.kitchen_window": "kitchen_zone",
    "sensor.bathroom_humidity": "bath_zone",
}
ZONE_ADJACENCY = {
    "kitchen_zone": ["living_zone"],
    "living_zone": ["kitchen_zone"],
    "bath_zone": [],
    "bedroom_zone": [],
}
