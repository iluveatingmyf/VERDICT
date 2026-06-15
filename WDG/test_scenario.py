"""
Test scenarios for WDG Function A and Function B.

These cases double as the worked examples we will show in the paper.
"""

from simulator import (
    load_wdg, forward_simulate, achieve_goal, format_trace
)


def section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def show_candidates(cands, target):
    if not cands:
        print("  (no candidates found)")
        return
    for i, c in enumerate(cands, 1):
        print(f"\n  Candidate {i}: action = {c.action}")
        print(f"    via capability: {c.via_capability}")
        print(f"    forward trace:")
        for s in c.forward_trace:
            for ef in s.effects:
                marker = "  <== TARGET" if ef.target == target else ""
                print(f"      hop {s.hop}: [{ef.via_edge_type:7s}] "
                      f"{ef.target} -> {ef.effect}{marker}")
        if c.side_effects:
            print(f"    side effects on other variables:")
            for ef in c.side_effects:
                print(f"      - {ef.target}: {ef.effect}")
        else:
            print(f"    side effects: none")


def main():
    wdg = load_wdg()

    # ------------------------------------------------------------------
    # Function A scenario 1: bathroom humidity spike fires R1, cascades to R2
    # ------------------------------------------------------------------
    section("Function A / Scenario 1: bathroom humidity rises above 80%")
    world_state = {
        "sensor.bathroom_humidity": 85,
        "fan.bathroom_fan": "off",
        "light.bathroom_light": "on",
        "sensor.temperature": 24,
        "sensor.outdoor_temperature": 18,
        "sensor.living_room_pm25": 30,
        "sensor.outdoor_aqi": 60,
        "switch.main_power": "on",
    }
    trigger = {"node": "sensor.bathroom_humidity",
               "event": {"kind": "numeric", "value": 85}}
    trace = forward_simulate(wdg, trigger, world_state)
    print(format_trace(trace))

    # ------------------------------------------------------------------
    # Function A scenario 2: kitchen smoke event, expect lock.unlock cascade
    # ------------------------------------------------------------------
    section("Function A / Scenario 2: kitchen smoke detected")
    world_state2 = {
        "binary_sensor.kitchen_smoke": "on",
        "lock.front_door": "locked",
        "binary_sensor.front_door_contact": "off",
        "switch.main_power": "on",
    }
    trigger2 = {"node": "binary_sensor.kitchen_smoke",
                "event": {"kind": "state", "to": "on"}}
    trace2 = forward_simulate(wdg, trigger2, world_state2)
    print(format_trace(trace2))

    # ------------------------------------------------------------------
    # Function A scenario 3: window opens; CONTEXTUAL effect on temperature.
    # ------------------------------------------------------------------
    section("Function A / Scenario 3a: open living-room window when it's hot indoors "
            "(T_in=28 > T_out=22)")
    world_state3a = {
        "cover.living_room_window": "closed",
        "sensor.temperature": 28,
        "sensor.outdoor_temperature": 22,
        "sensor.living_room_pm25": 30,
        "sensor.outdoor_aqi": 60,
        "switch.main_power": "on",
        "climate.main_hvac": "heat",
    }
    # Simulate the user opening the window: that *is* the trigger event.
    # We set the new device state and let forward_simulate propagate CAUSAL edges.
    world_state3a["cover.living_room_window"] = "open"
    trigger3a = {"node": "cover.living_room_window",
                 "event": {"kind": "state", "to": "open"}}
    trace3a = forward_simulate(wdg, trigger3a, world_state3a)
    print(format_trace(trace3a))

    section("Function A / Scenario 3b: same action, but now T_in=18 < T_out=30")
    world_state3b = dict(world_state3a)
    world_state3b["sensor.temperature"] = 18
    world_state3b["sensor.outdoor_temperature"] = 30
    trace3b = forward_simulate(wdg, trigger3a, world_state3b)
    print(format_trace(trace3b))

    # ------------------------------------------------------------------
    # Function A scenario 4: inhibition by power gating
    # ------------------------------------------------------------------
    section("Function A / Scenario 4: motion fires R26 to turn on light, "
            "but main_power=off inhibits it")
    world_state4 = {
        "binary_sensor.living_room_motion": "on",
        "light.living_room_light": "off",
        "sensor.living_room_illuminance": 20,
        "switch.main_power": "off",
    }
    trigger4 = {"node": "binary_sensor.living_room_motion",
                "event": {"kind": "state", "to": "on"}}
    trace4 = forward_simulate(wdg, trigger4, world_state4)
    print(format_trace(trace4))

    # ------------------------------------------------------------------
    # Function B scenario 1: "I want to decrease PM2.5 in the living room"
    # ------------------------------------------------------------------
    section("Function B / Scenario 1: decrease sensor.living_room_pm25 "
            "(indoor=90, outdoor=40 -> outdoor cleaner)")
    ws_b1 = {
        "sensor.living_room_pm25": 90,
        "sensor.outdoor_aqi": 40,
        "sensor.temperature": 24,
        "sensor.outdoor_temperature": 22,
        "switch.main_power": "on",
        "fan.air_purifier": "off",
        "cover.living_room_window": "closed",
    }
    cands_b1 = achieve_goal(wdg, "sensor.living_room_pm25", "DECREASE", ws_b1)
    show_candidates(cands_b1, "sensor.living_room_pm25")

    section("Function B / Scenario 1b: same goal, but outdoor is dirtier (outdoor=130)")
    ws_b1b = dict(ws_b1)
    ws_b1b["sensor.outdoor_aqi"] = 130
    cands_b1b = achieve_goal(wdg, "sensor.living_room_pm25", "DECREASE", ws_b1b)
    show_candidates(cands_b1b, "sensor.living_room_pm25")

    # ------------------------------------------------------------------
    # Function B scenario 2: "I want to decrease the indoor temperature"
    # ------------------------------------------------------------------
    section("Function B / Scenario 2: decrease sensor.temperature "
            "(indoor=28, outdoor=22 -> opening windows helps)")
    ws_b2 = {
        "sensor.temperature": 28,
        "sensor.outdoor_temperature": 22,
        "sensor.living_room_pm25": 30,
        "sensor.outdoor_aqi": 60,
        "switch.main_power": "on",
        "climate.main_hvac": "off",
    }
    cands_b2 = achieve_goal(wdg, "sensor.temperature", "DECREASE", ws_b2)
    show_candidates(cands_b2, "sensor.temperature")

    # ------------------------------------------------------------------
    # Function B scenario 3: "I want to decrease kitchen CO"
    # ------------------------------------------------------------------
    section("Function B / Scenario 3: decrease sensor.kitchen_co")
    ws_b3 = {
        "sensor.kitchen_co": 80,
        "switch.range_hood": "off",
        "fan.ventilation_fan": "off",
        "cover.kitchen_window": "closed",
        "sensor.temperature": 24,
        "sensor.outdoor_temperature": 18,
        "switch.main_power": "on",
    }
    cands_b3 = achieve_goal(wdg, "sensor.kitchen_co", "DECREASE", ws_b3)
    show_candidates(cands_b3, "sensor.kitchen_co")


if __name__ == "__main__":
    main()