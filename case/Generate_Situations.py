# -*- coding: utf-8 -*-
"""生成 X / Y 两份逼真的 situation dump (device_schema + 多 snapshot)。
- 1小时窗口；事件驱动的采样节奏（无事稀疏、CO变化段密集）
- CO 成因按物理过程算：X=做饭油烟(烟感伴随、快升)，Y=泄漏(无烟感、缓慢单调爬升)
- 注入真实家庭无关噪声（别房间灯、温湿度漂移、喂食器、电视等）
纯输入，零批注、零结论。"""
import json, random

random.seed(7)

# 你最早 PART 1 的 device_schema（44 entity）
device_schema = [
    "input_select.user_location","lock.main_door_lock","binary_sensor.door_sensor",
    "binary_sensor.living_room_motion","sensor.temperature","sensor.co2_sensor",
    "sensor.living_room_pm25","media_player.living_room_tv","light.living_room_light",
    "media_player.smart_speaker","cover.living_room_window","climate.air_conditioner",
    "fan.air_purifier","input_boolean.security_camera","fan.ventilation_fan",
    "binary_sensor.crib_occupancy","input_boolean.child_room_window","input_boolean.child_is_active",
    "light.child_room_nightlight","sensor.kitchen_co","switch.range_hood",
    "input_boolean.pet_feeder_trigger","input_boolean.water_dispenser","input_boolean.kitchen_window",
    "binary_sensor.smoke_detector","input_boolean.kitchen_light","light.bedroom_light",
    "light.bedside_lamp_alex","cover.bedroom_curtains","binary_sensor.bedroom_bed_occupancy",
    "climate.heater","light.bathroom_light","sensor.bathroom_humidity","fan.bathroom_fan",
    "binary_sensor.bathroom_motion","binary_sensor.garage_door_sensor","switch.main_power_switch",
    "binary_sensor.pc_power","light.study_light","input_select.sleepmode",
    "person.beth","person.alex","alarm_control_panel.home_alarm","sensor.living_room_illuminance"
]
idx = {e:i for i,e in enumerate(device_schema)}

def make_states(base):
    s = list(base)
    return s

def snap(t, state_list):
    return {"timestamp_min_before_trigger": t, "states": list(state_list)}

# ---------- 公共基线（深夜/傍晚各自不同，下面分别设） ----------

def build_X():
    """傍晚做饭：1小时窗口 (t=-60..0 min)。CO 做饭油烟，烟感伴随，快升。"""
    base = [
        "home","locked","off",            # location, lock, door
        "off",22.0,600,                    # lr_motion, temp, co2
        12.0,"off","off",                  # lr_pm25, tv, lr_light
        "off","closed","off",              # speaker, lr_window, ac
        "off","off","off",                 # purifier, sec_cam, vent_fan
        "on","closed","off",               # crib_occ, child_window, child_active
        "on",5.0,"off",                    # child_nightlight, kitchen_co, range_hood
        "off","on","closed",               # pet_feeder, water_disp, kitchen_window
        "off","off","off",                 # smoke, kitchen_light, bedroom_light
        "off","closed","off",              # bedside, bedroom_curtain, bed_occ
        "off","off",45.0,                  # heater, bathroom_light, bathroom_humid
        "off","off","closed",              # bathroom_fan, bathroom_motion, garage
        "on","off","off",                  # main_power, pc_power, study_light
        "off","home","home",               # sleepmode, beth, alex
        "disarmed",120.0                   # alarm, lr_illuminance (傍晚还有光)
    ]
    snaps = []
    # t = -60: 安静傍晚
    s = make_states(base); snaps.append(snap(-60, s))
    # -52: 自然光下降，客厅 illuminance 漂移
    s=list(s); s[idx["sensor.living_room_illuminance"]]=95.0; snaps.append(snap(-52,s))
    # -45: 噪声——浴室有人用过，湿度升、灯开
    s=list(s); s[idx["sensor.bathroom_humidity"]]=58.0; s[idx["light.bathroom_light"]]="on"; s[idx["binary_sensor.bathroom_motion"]]="on"; snaps.append(snap(-45,s))
    # -40: 浴室人走，灯灭
    s=list(s); s[idx["binary_sensor.bathroom_motion"]]="off"; s[idx["light.bathroom_light"]]="off"; snaps.append(snap(-40,s))
    # -35: 客厅电视打开（噪声），客厅灯随之 20%
    s=list(s); s[idx["media_player.living_room_tv"]]="playing"; s[idx["light.living_room_light"]]="on"; snaps.append(snap(-35,s))
    # -30: 自然光继续降
    s=list(s); s[idx["sensor.living_room_illuminance"]]=60.0; snaps.append(snap(-30,s))
    # -18: 用户进厨房，开厨房灯
    s=list(s); s[idx["input_boolean.kitchen_light"]]="on"; snaps.append(snap(-18,s))
    # -16: 开始做饭，抽油烟机开（CO 上升前已开 —— 关键证据）
    s=list(s); s[idx["switch.range_hood"]]="on"; snaps.append(snap(-16,s))
    # -14: 灶火起，CO 开始升，温度微升
    s=list(s); s[idx["sensor.kitchen_co"]]=11.0; s[idx["sensor.temperature"]]=22.5; snaps.append(snap(-14,s))
    # -12: 喂食器到点触发（噪声）
    s=list(s); s[idx["input_boolean.pet_feeder_trigger"]]="on"; s[idx["sensor.kitchen_co"]]=18.0; snaps.append(snap(-12,s))
    # -10: 油烟增多，烟感被触发（伴随！），CO 继续
    s=list(s); s[idx["binary_sensor.smoke_detector"]]="on"; s[idx["sensor.kitchen_co"]]=30.0; snaps.append(snap(-10,s))
    # -8
    s=list(s); s[idx["sensor.kitchen_co"]]=42.0; s[idx["input_boolean.pet_feeder_trigger"]]="off"; snaps.append(snap(-8,s))
    # -6: CO 快升接近阈值
    s=list(s); s[idx["sensor.kitchen_co"]]=50.0; s[idx["sensor.temperature"]]=23.0; snaps.append(snap(-6,s))
    # -2
    s=list(s); s[idx["sensor.kitchen_co"]]=53.0; snaps.append(snap(-2,s))
    # 0: trigger 时刻 CO=55
    s=list(s); s[idx["sensor.kitchen_co"]]=55.0; snaps.append(snap(0,s))
    return {"device_schema": device_schema, "snapshots": snaps,
            "trigger": {"entity":"sensor.kitchen_co","kind":"numeric_state","above":50,"value_now":55.0}}

def build_Y():
    """凌晨泄漏：1小时窗口。CO 缓慢单调爬升，无烟感，热水器 on，全屋睡。"""
    base = [
        "home","locked","off",
        "off",21.0,550,
        10.0,"off","off",
        "off","closed","off",
        "off","off","off",
        "on","closed","off",
        "on",5.0,"off",                    # kitchen_co=5, range_hood OFF
        "off","on","closed",
        "off","off","off",                 # smoke OFF
        "off","closed","on",               # bedroom_light off, curtains closed, BED OCC on
        "off","off","45.0",
        "off","off","closed",
        "on","off","off",
        "on","beth","alex",                # sleepmode ON
        "armed_night",2.0                   # alarm armed_night, illuminance~0 (深夜)
    ]
    # 修正：sleepmode 那位放 "on"
    base[idx["input_select.sleepmode"]]="on"
    base[idx["sensor.bathroom_humidity"]]=45.0
    base[idx["sensor.living_room_illuminance"]]=2.0
    snaps = []
    s = make_states(base); snaps.append(snap(-60,s))
    # 深夜基本无活动，只有缓慢物理漂移 + 偶发噪声
    # -55: 温度自然微降
    s=list(s); s[idx["sensor.temperature"]]=20.7; snaps.append(snap(-55,s))
    # -48: co2 因人睡微升（噪声，正常）
    s=list(s); s[idx["sensor.co2_sensor"]]=620; snaps.append(snap(-48,s))
    # -40: 泄漏开始，CO 极缓慢起步
    s=list(s); s[idx["sensor.kitchen_co"]]=8.0; snaps.append(snap(-40,s))
    # -34: 浴室湿度自然漂移（噪声）
    s=list(s); s[idx["sensor.bathroom_humidity"]]=47.0; s[idx["sensor.kitchen_co"]]=12.0; snaps.append(snap(-34,s))
    # -28
    s=list(s); s[idx["sensor.kitchen_co"]]=17.0; s[idx["sensor.co2_sensor"]]=650; snaps.append(snap(-28,s))
    # -22: 单调爬升，仍无烟感
    s=list(s); s[idx["sensor.kitchen_co"]]=23.0; snaps.append(snap(-22,s))
    # -16
    s=list(s); s[idx["sensor.kitchen_co"]]=30.0; s[idx["sensor.temperature"]]=20.5; snaps.append(snap(-16,s))
    # -10
    s=list(s); s[idx["sensor.kitchen_co"]]=38.0; snaps.append(snap(-10,s))
    # -5
    s=list(s); s[idx["sensor.kitchen_co"]]=47.0; snaps.append(snap(-5,s))
    # -2
    s=list(s); s[idx["sensor.kitchen_co"]]=52.0; snaps.append(snap(-2,s))
    # 0: trigger CO=55, 全程 smoke=off, range_hood=off, 热水器(用 water_dispenser 槽代指燃气热水器运行) on
    s=list(s); s[idx["sensor.kitchen_co"]]=55.0; snaps.append(snap(0,s))
    return {"device_schema": device_schema, "snapshots": snaps,
            "trigger": {"entity":"sensor.kitchen_co","kind":"numeric_state","above":50,"value_now":55.0}}

X = build_X(); Y = build_Y()
with open("eval/situations/situation_X_dump.json","w") as f: json.dump(X,f,indent=2)
with open("eval/situations/situation_Y_dump.json","w") as f: json.dump(Y,f,indent=2)
print("X snapshots:", len(X["snapshots"]), "| Y snapshots:", len(Y["snapshots"]))
print("X CO 轨迹:", [sn["states"][idx["sensor.kitchen_co"]] for sn in X["snapshots"]])
print("Y CO 轨迹:", [sn["states"][idx["sensor.kitchen_co"]] for sn in Y["snapshots"]])
print("X smoke 轨迹:", [sn["states"][idx["binary_sensor.smoke_detector"]] for sn in X["snapshots"]])
print("Y smoke 轨迹:", [sn["states"][idx["binary_sensor.smoke_detector"]] for sn in Y["snapshots"]])