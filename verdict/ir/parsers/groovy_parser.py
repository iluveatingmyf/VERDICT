"""
Groovy / SmartThings rule parser — regex-based, ~70% coverage target.

Extracts triggers (subscribe calls), actions (device commands), and capability
bindings from SmartThings Groovy SmartApp source files.

Design constraints (CLAUDE.md §15):
- Do NOT build a full Groovy parser. Regex + lightweight heuristics only.
- Drop files with unsupported patterns; log the reason.
- 70% corpus coverage is sufficient.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vocabulary mappings
# ---------------------------------------------------------------------------

# SmartThings capability class suffix → VERDICT capability (§6)
_CAPABILITY_CLASS: dict[str, str] = {
    "motionSensor": "motion",
    "switch": "switch",
    "switchLevel": "light",
    "colorControl": "light",
    "colorTemperature": "light",
    "contactSensor": "contact",
    "presenceSensor": "presence",
    "lock": "lock",
    "thermostat": "temperature",
    "temperatureMeasurement": "temperature",
    "illuminanceMeasurement": "illuminance",
    "smokeDetector": "smoke_detector",
    "carbonMonoxideDetector": "co_detector",
}

# subscribe event string → (capability, event)
_EVENT_MAP: dict[str, tuple[str, str]] = {
    "motion.active": ("motion", "active"),
    "motion.inactive": ("motion", "inactive"),
    "motion": ("motion", "active"),          # unqualified: default to active
    "contact.open": ("contact", "open"),
    "contact.closed": ("contact", "closed"),
    "contact": ("contact", "open"),
    "switch.on": ("switch", "on"),
    "switch.off": ("switch", "off"),
    "switch": ("switch", "on"),
    "presence.present": ("presence", "present"),
    "presence.not present": ("presence", "not_present"),
    "presence": ("presence", "present"),
    "lock.locked": ("lock", "lock"),
    "lock.unlocked": ("lock", "unlock"),
    "lock": ("lock", "lock"),
    "smoke.detected": ("smoke_detector", "detected"),
    "smoke.clear": ("smoke_detector", "clear"),
    "smoke.tested": ("smoke_detector", "detected"),
    "smoke": ("smoke_detector", "detected"),
    "carbonMonoxide.detected": ("co_detector", "detected"),
    "carbonMonoxide.clear": ("co_detector", "clear"),
    "carbonMonoxide": ("co_detector", "detected"),
    "illuminance": ("illuminance", "measured"),
    "temperature": ("temperature", "measured"),
}

# device method name → (capability, command)
_COMMAND_MAP: dict[str, tuple[str, str]] = {
    "on": ("switch", "on"),
    "off": ("switch", "off"),
    "lock": ("lock", "lock"),
    "unlock": ("lock", "unlock"),
    "setLevel": ("light", "set_level"),
    "setColor": ("light", "set_color"),
    "setColorTemperature": ("light", "set_color"),
    "setHeatingSetpoint": ("temperature", "set_temperature"),
    "setCoolingSetpoint": ("temperature", "set_temperature"),
    "setThermostatSetpoint": ("temperature", "set_temperature"),
}

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_RE_DEFINITION = re.compile(
    r'definition\s*\([^)]*name\s*:\s*["\']([^"\']+)["\'][^)]*\)', re.DOTALL
)
_RE_DESCRIPTION = re.compile(
    r'definition\s*\(.*?description\s*:\s*["\']([^"\']+)["\']', re.DOTALL
)
_RE_INPUT = re.compile(
    r'input\s+["\'](\w+)["\'],\s*["\']capability\.(\w+)["\']'
)
_RE_SUBSCRIBE = re.compile(
    r'subscribe\s*\(\s*(\w+)\s*,\s*["\']([^"\']+)["\']'
)
_RE_DEVICE_CMD = re.compile(
    r'(\w+)\s*\.\s*(on|off|lock|unlock|setLevel|setColor|setColorTemperature'
    r'|setHeatingSetpoint|setCoolingSetpoint|setThermostatSetpoint)\s*\(([^)]*)\)'
)
_RE_SEND_PUSH = re.compile(
    r'sendPush\s*\(([^)]*)\)'
)
_RE_SEND_NOTIFICATION = re.compile(
    r'sendNotification(?:ToContacts)?\s*\(([^)]*)\)'
)
_RE_SEND_SMS = re.compile(
    r'sendSms\s*\([^,)]+,\s*([^)]+)\)'
)
_RE_RUNIN = re.compile(
    r'runIn\s*\(\s*(\d+)\s*,\s*(\w+)'
)

# ---------------------------------------------------------------------------
# Output dataclass (matches IR schema §5, serialisable to YAML)
# ---------------------------------------------------------------------------

@dataclass
class ParsedTrigger:
    capability: str
    entity_ref: str
    event: str
    params: dict = field(default_factory=dict)


@dataclass
class ParsedCondition:
    capability: str
    entity_ref: str
    predicate: str
    value: object


@dataclass
class ParsedAction:
    capability: str
    entity_ref: str
    command: str
    params: dict = field(default_factory=dict)
    delay_ms: int = 0


@dataclass
class ParsedRule:
    """Intermediate result before IR YAML serialisation."""
    name: str
    description_oneliner: str
    raw_path: str
    triggers: list[ParsedTrigger]
    conditions: list[ParsedCondition]
    actions: list[ParsedAction]
    capabilities_read: list[str]
    capabilities_written: list[str]
    drop_reason: Optional[str] = None   # set when rule is unsupported


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_file(path: Path) -> Optional[ParsedRule]:
    """
    Parse a single Groovy SmartApp file.

    Returns a ParsedRule on success, or None with a logged warning if the
    file cannot be usefully parsed (dropped per §5.2 "Drop, don't fudge").
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None

    return parse_source(source, str(path))


def parse_source(source: str, raw_path: str = "<string>") -> Optional[ParsedRule]:
    """
    Parse Groovy SmartApp source text into a ParsedRule.

    Returns None and logs a warning if the file must be dropped.
    """
    # --- app name --------------------------------------------------------
    m = _RE_DEFINITION.search(source)
    if not m:
        logger.warning("DROP %s: no definition() block found", raw_path)
        return None
    name = m.group(1).strip()

    m_desc = _RE_DESCRIPTION.search(source)
    description = m_desc.group(1).strip() if m_desc else name

    # --- capability input bindings: varname → capability -----------------
    var_cap: dict[str, str] = {}
    for m in _RE_INPUT.finditer(source):
        var_name, cap_class = m.group(1), m.group(2)
        verdict_cap = _CAPABILITY_CLASS.get(cap_class)
        if verdict_cap:
            var_cap[var_name] = verdict_cap
        else:
            logger.debug(
                "%s: unknown capability class %r for input %r — skipped",
                raw_path, cap_class, var_name,
            )

    # --- triggers: subscribe(...) ----------------------------------------
    triggers: list[ParsedTrigger] = []
    for m in _RE_SUBSCRIBE.finditer(source):
        var_name, event_str = m.group(1), m.group(2)
        cap_event = _EVENT_MAP.get(event_str.lower().strip())
        if cap_event is None:
            logger.debug(
                "%s: unknown event %r in subscribe(%s, ...) — skipped",
                raw_path, event_str, var_name,
            )
            continue
        capability, event = cap_event
        entity_ref = f"${var_name}"
        # Reconcile: if var has a known cap binding, prefer it; else use event-derived
        if var_name in var_cap:
            capability = var_cap[var_name]
        triggers.append(ParsedTrigger(
            capability=capability,
            entity_ref=entity_ref,
            event=event,
        ))

    # --- actions: device command calls -----------------------------------
    actions: list[ParsedAction] = []
    seen_actions: set[tuple] = set()   # deduplicate identical calls

    # Device method calls: var.command(args)
    for m in _RE_DEVICE_CMD.finditer(source):
        var_name, method, args_raw = m.group(1), m.group(2), m.group(3).strip()
        cmd_info = _COMMAND_MAP.get(method)
        if cmd_info is None:
            continue
        capability, command = cmd_info
        # Override capability from known var binding if available
        if var_name in var_cap:
            capability = var_cap[var_name]
        params: dict = {}
        if args_raw:
            params["raw_arg"] = args_raw
        key = (var_name, command)
        if key not in seen_actions:
            seen_actions.add(key)
            actions.append(ParsedAction(
                capability=capability,
                entity_ref=f"${var_name}",
                command=command,
                params=params,
            ))

    # sendPush / sendNotification / sendSms → notification capability
    for pattern in (_RE_SEND_PUSH, _RE_SEND_NOTIFICATION, _RE_SEND_SMS):
        for m in pattern.finditer(source):
            msg_raw = m.group(1).strip()
            key = ("$notification", "send_notification")
            if key not in seen_actions:
                seen_actions.add(key)
                actions.append(ParsedAction(
                    capability="notification",
                    entity_ref="$notification",
                    command="send_notification",
                    params={"message": msg_raw} if msg_raw else {},
                ))

    # runIn(N, handler) adds a delay on the first action it appears before — note only
    for m in _RE_RUNIN.finditer(source):
        delay_sec = int(m.group(1))
        # We can't know which action it delays without full AST; annotate as metadata
        if actions:
            actions[-1].delay_ms = max(actions[-1].delay_ms, delay_sec * 1000)

    # --- drop check: must have at least one trigger or action ------------
    if not triggers and not actions:
        logger.warning(
            "DROP %s: no usable subscribe() triggers or device commands found",
            raw_path,
        )
        return None

    # --- derived fields --------------------------------------------------
    caps_read: set[str] = {t.capability for t in triggers}
    # conditions would add read caps too — skipped in regex tier
    caps_written: set[str] = {a.capability for a in actions}

    return ParsedRule(
        name=name,
        description_oneliner=description[:120],
        raw_path=raw_path,
        triggers=triggers,
        conditions=[],    # regex tier cannot reliably extract conditions
        actions=actions,
        capabilities_read=sorted(caps_read),
        capabilities_written=sorted(caps_written),
    )


# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------

def parse_directory(
    root: Path,
    *,
    glob: str = "**/*.groovy",
) -> tuple[list[ParsedRule], list[tuple[Path, str]]]:
    """
    Recursively parse all Groovy files under *root*.

    Returns (parsed_rules, dropped_files) where dropped_files is a list of
    (path, reason) pairs for rules that could not be parsed.
    """
    parsed: list[ParsedRule] = []
    dropped: list[tuple[Path, str]] = []

    for path in sorted(root.glob(glob)):
        rule = parse_file(path)
        if rule is None:
            dropped.append((path, "parse_failed"))
        else:
            parsed.append(rule)

    logger.info(
        "parse_directory(%s): %d parsed, %d dropped",
        root, len(parsed), len(dropped),
    )
    return parsed, dropped
