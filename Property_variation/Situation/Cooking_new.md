{
  "meta": {
    "situation_id": "sit_20250528_1940_co",
    "now": "2025-05-28T19:40:00",
    "time_of_day": "evening"
  },

  // 一句话说明:只描述,不下结论(不出现"安全/火灾/应否决"这类词)
  "description": "晚饭时段,用户正在厨房做饭(抽油烟机与厨房灯已开)。厨房 CO 在两分钟内由 5 升至 55 ppm,期间烟感被触发,厨房温度正常。儿童房有婴儿在睡。自动化规则因 CO 升高拟开启厨房窗户通风。",

  // 决策点:被判断的对象
  "decision_point": {
    "trigger": {
      "entity": "input_number.co_sensor", "zone": "kitchen",
      "kind": "sensor_jump", "from": 5.0, "to": 55.0, "unit": "ppm", "at": "19:38"
    },
    "proposed_action": {
      "rule_id": "auto_safety_co_ventilation",
      "service": "input_boolean.turn_on",
      "target": "input_boolean.kitchen_window",
      "params": {},
      "designed_intent": "开窗通风以降低 CO"     // 规则初衷,非结论
    }
  },

  // 用户活动标签(你那条常驻序列模型的输出)
  "activity": {
    "label": "cooking", "confidence": 0.9, "since": "19:32",
    "evidence": ["range_hood=on", "kitchen_light=on"], "source": "sequence_model"
  },

  // 人物/脆弱人群
  "occupants": [
    { "who": "person.alex", "location": "kitchen", "state": "awake" }
  ],
  "vulnerable": [
    { "who": "infant", "zone": "child_room", "via": "binary_sensor.crib_occupancy=on" }
  ],

  // 世界状态:snapshot(空间的面)+ deltas(时间的线)
  "world_state": {
    "snapshot": {
      "kitchen": {
        "range_hood": "on",
        "kitchen_window": "closed",
        "kitchen_light": "on",
        "smoke_detector": "on",
        "co":   { "value": 55, "unit": "ppm", "ref_normal": "<9", "ref_danger": ">70" },
        "temp": { "value": 22, "unit": "C",   "ref_normal": "18-26" }
      },
      "child_room": {
        "child_room_window": "closed",
        "nightlight": "on",
        "crib_occupancy": "on"
      }
    },
    "deltas": [
      { "at": "19:32", "entity": "switch.range_hood",        "zone": "kitchen", "from": "off", "to": "on" },
      { "at": "19:36", "entity": "binary_sensor.smoke_detector","zone":"kitchen","from": "off", "to": "on" },
      { "at": "19:38", "entity": "input_number.co_sensor",   "zone": "kitchen", "from": 5.0, "to": 55.0, "unit": "ppm" }
    ]
  }
}