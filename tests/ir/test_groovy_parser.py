"""Tests for verdict/ir/parsers/groovy_parser.py."""

import pytest
from verdict.ir.parsers.groovy_parser import parse_source, ParsedRule

# ---------------------------------------------------------------------------
# Fixtures: minimal Groovy source snippets
# ---------------------------------------------------------------------------

MOTION_LIGHT = """
definition(
    name: "Motion Light",
    description: "Turn on light when motion detected."
)
preferences {
    input "motion1", "capability.motionSensor", title: "Where?"
    input "switch1", "capability.switch", multiple: true
}
def installed() { subscribe(motion1, "motion.active", motionHandler) }
def motionHandler(evt) { switch1.on() }
"""

CONTACT_LOCK = """
definition(name: "Door Lock on Close", description: "Lock door when contact closes.")
preferences {
    input "contact1", "capability.contactSensor", title: "Sensor"
    input "lock1", "capability.lock", title: "Lock"
}
def installed() { subscribe(contact1, "contact.closed", handler) }
def handler(evt) { lock1.lock() }
"""

PRESENCE_NOTIFY = """
definition(name: "Welcome Home", description: "Notify on arrival.")
preferences {
    input "presence1", "capability.presenceSensor", title: "Who?"
}
def installed() { subscribe(presence1, "presence.present", arrivalHandler) }
def arrivalHandler(evt) { sendPush("Welcome home!") }
"""

MULTI_TRIGGER = """
definition(name: "Multi Trigger", description: "Motion or contact triggers light.")
preferences {
    input "motion1", "capability.motionSensor"
    input "contact1", "capability.contactSensor"
    input "lights", "capability.switch"
}
def installed() {
    subscribe(motion1, "motion.active", handler)
    subscribe(contact1, "contact.open", handler)
}
def handler(evt) { lights.on() }
"""

SMOKE_ALARM = """
definition(name: "Smoke Alert", description: "Notify on smoke detection.")
preferences {
    input "smoke1", "capability.smokeDetector"
}
def installed() { subscribe(smoke1, "smoke.detected", smokeHandler) }
def smokeHandler(evt) { sendNotification("Smoke detected!") }
"""

NO_DEFINITION = """
preferences { input "x", "capability.switch" }
def installed() { subscribe(x, "switch.on", h) }
def h(evt) { x.on() }
"""

NO_TRIGGERS_NO_ACTIONS = """
definition(name: "Empty App", description: "Does nothing.")
preferences {}
def installed() { log.debug "hello" }
"""

UNLOCK_LIGHT = """
definition(name: "Unlock and Light", description: "Unlock door and turn on light.")
preferences {
    input "lock1", "capability.lock"
    input "light1", "capability.switchLevel"
}
def installed() { subscribe(lock1, "lock.unlocked", handler) }
def handler(evt) {
    lock1.unlock()
    light1.setLevel(80)
}
"""

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParseSource:
    def test_motion_light_triggers(self):
        rule = parse_source(MOTION_LIGHT)
        assert rule is not None
        assert len(rule.triggers) == 1
        t = rule.triggers[0]
        assert t.capability == "motion"
        assert t.entity_ref == "$motion1"
        assert t.event == "active"

    def test_motion_light_actions(self):
        rule = parse_source(MOTION_LIGHT)
        assert rule is not None
        assert len(rule.actions) == 1
        a = rule.actions[0]
        assert a.capability == "switch"
        assert a.entity_ref == "$switch1"
        assert a.command == "on"

    def test_motion_light_derived(self):
        rule = parse_source(MOTION_LIGHT)
        assert rule is not None
        assert "motion" in rule.capabilities_read
        assert "switch" in rule.capabilities_written

    def test_contact_lock(self):
        rule = parse_source(CONTACT_LOCK)
        assert rule is not None
        assert rule.triggers[0].capability == "contact"
        assert rule.triggers[0].event == "closed"
        assert rule.actions[0].capability == "lock"
        assert rule.actions[0].command == "lock"

    def test_presence_notification(self):
        rule = parse_source(PRESENCE_NOTIFY)
        assert rule is not None
        assert rule.triggers[0].capability == "presence"
        assert rule.triggers[0].event == "present"
        assert rule.actions[0].capability == "notification"
        assert rule.actions[0].command == "send_notification"

    def test_multi_trigger(self):
        rule = parse_source(MULTI_TRIGGER)
        assert rule is not None
        assert len(rule.triggers) == 2
        caps = {t.capability for t in rule.triggers}
        assert caps == {"motion", "contact"}

    def test_smoke_sendnotification(self):
        rule = parse_source(SMOKE_ALARM)
        assert rule is not None
        assert rule.triggers[0].capability == "smoke_detector"
        assert rule.actions[0].capability == "notification"

    def test_unlock_and_setlevel(self):
        rule = parse_source(UNLOCK_LIGHT)
        assert rule is not None
        commands = {a.command for a in rule.actions}
        assert "unlock" in commands
        assert "set_level" in commands
        assert "light" in rule.capabilities_written

    def test_name_extracted(self):
        rule = parse_source(MOTION_LIGHT)
        assert rule is not None
        assert rule.name == "Motion Light"

    def test_no_definition_returns_none(self):
        rule = parse_source(NO_DEFINITION)
        assert rule is None

    def test_no_triggers_no_actions_returns_none(self):
        rule = parse_source(NO_TRIGGERS_NO_ACTIONS)
        assert rule is None

    def test_conditions_empty_at_regex_tier(self):
        # Regex tier cannot extract conditions reliably; must be empty
        rule = parse_source(MOTION_LIGHT)
        assert rule is not None
        assert rule.conditions == []


class TestRealCorpusSample:
    """Smoke-test against the Soteria BrightenMyPath rule (motion → switch.on/off)."""

    BRIGHTEN = """
definition(
    name: "Brighten My Path",
    namespace: "Soteria",
    description: "Turn your lights on when motion is detected."
)
preferences {
    section("When there's movement...") {
        input "motion1", "capability.motionSensor", title: "Where?", multiple: true
    }
    section("Turn on a light...") {
        input "switch1", "capability.switch", multiple: true
    }
}
def installed() { subscribe(motion1, "motion.active", motionActiveHandler) }
def updated()   { unsubscribe(); subscribe(motion1, "motion.active", motionActiveHandler) }
def motionActiveHandler(evt) {
    switch1.on()
    switch1.off()
}
"""

    def test_brighten_parses(self):
        rule = parse_source(self.BRIGHTEN)
        assert rule is not None

    def test_brighten_single_trigger(self):
        rule = parse_source(self.BRIGHTEN)
        assert rule is not None
        # subscribe appears twice (installed + updated) but same device/event
        triggers = rule.triggers
        assert any(t.event == "active" and t.capability == "motion" for t in triggers)

    def test_brighten_on_and_off_actions(self):
        rule = parse_source(self.BRIGHTEN)
        assert rule is not None
        commands = {a.command for a in rule.actions}
        assert "on" in commands
        assert "off" in commands
