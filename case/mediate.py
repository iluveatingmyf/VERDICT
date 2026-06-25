# -*- coding: utf-8 -*-
"""
Stage 2+3: 冲突消解 + WDG落地 + 生成可复用规则。
输入：Stage1 的激活结果(activation JSON) + proposed_action + 库 + WDG。
流程：
  1. 收集 active σ，按 protect_target 优先级排序（激活的property = 裁决依据）
  2. 用 WDG(Function A) 前向模拟 proposed_action 的真实后果 Δ(a)
  3. 判断 proposed_action 是否违反任何 active σ 的需求（用 σ 的 violated 字段 + Δ 印证）
  4. 若违反高优先级需求 → 否决；并(可选)用 Function B 在 WDG 上找一个
     既服务 active 需求、又不违反更高需求的替代动作
  5. 用 DSL 表达最终处置；grounding 成带护栏可复用规则

  python mediate.py --activation <激活json> --situation <situation json>。
"""
import sys, json, argparse
sys.path.insert(0, "core")
from simulator import load_wdg, forward_simulate, achieve_goal, format_trace

PRIORITY = ["personal_safety","physical_security","privacy","task_completion","comfort","energy"]
def prio(pt): return PRIORITY.index(pt) if pt in PRIORITY else len(PRIORITY)

# proposed_action 的 service -> 它把目标设备置成什么状态（用于 WDG 模拟）
SERVICE_RESULT = {"cover.open_cover":"open","cover.close_cover":"closed",
                  "lock.lock":"locked","lock.unlock":"unlocked",
                  "fan.turn_on":"on","switch.turn_on":"on","light.turn_on":"on"}

def load(path): return json.load(open(path))

def mediate(activation_path, situation_path, lib_path="library/confirmed_properties.json",
            wdg_path="data/wdg.json"):
    act = load(activation_path)          # Stage1 输出
    sit = load(situation_path)
    lib = {s["sigma_id"]: s for s in load(lib_path)["sigmas"]}
    wdg = load_wdg(wdg_path)

    pa = sit["proposed_action"]
    svc = pa["service"]; target = pa["target"]
    print("="*72)
    print(f"提议动作: {pa['rule_id']}  ->  {svc}({target})")
    print(f"   设计初衷: {pa.get('designed_intent','?')}")
    print("="*72)

    # ---- 1. 收集 active σ（这就是“评审意见”）----
    active = [a for a in act["activations"] if a["verdict"]=="active"]
    print(f"\n[1] Stage1 激活的需求（评审意见，共 {len(active)} 条）：")
    enriched=[]
    for a in active:
        sid=a["sigma_id"]; s=lib.get(sid,{})
        pt=s.get("protect_target","?")
        enriched.append({**a, "protect_target":pt,
                         "abstract_action":s.get("abstract_action","?"),
                         "from_property":s.get("from_property","?")})
        flag = "  ⚠️被提议动作违反" if a.get("violated_by_proposed_action") else ""
        print(f"   [{pt:17s}] {sid}{flag}")

    # ---- 2. WDG 前向模拟提议动作的真实后果 Δ(a) ----
    print(f"\n[2] WDG 前向模拟提议动作的真实后果 Δ(a)：")
    new_state = SERVICE_RESULT.get(svc,"fired")
    ws = build_world_state(sit)            # 从 situation 末帧抽世界状态
    ws[target]=new_state
    delta = forward_simulate(wdg, {"node":target,"event":{"kind":"state","to":new_state}}, ws)
    print(format_trace(delta) if delta else "   (无连锁后果)")

    # ---- 3. 冲突消解：被违反的 active σ 里，谁优先级最高 ----
    violated = [e for e in enriched if e.get("violated_by_proposed_action")]
    print(f"\n[3] 冲突消解：")
    if not violated:
        print("   提议动作未违反任何 active 需求 -> 放行 (pass-through)")
        decision = {"verdict":"ALLOW","winning_sigma":None}
    else:
        violated.sort(key=lambda e: prio(e["protect_target"]))
        winner = violated[0]
        # 还要看：有没有“支持该动作”的 active σ（动作声称服务的目的）且其前提成立
        supporters = [e for e in enriched
                      if not e.get("violated_by_proposed_action")
                      and e["protect_target"]==winner["protect_target"]]
        labels = ", ".join("%s:%s" % (e["protect_target"], e["sigma_id"].split(".")[-1]) for e in violated)
        print("   被违反的需求(按优先级): " + labels)
        print(f"   胜出(最高优先级被违反者): {winner['sigma_id']}  [{winner['protect_target']}]")
        print(f"   -> 提议动作违反了最高优先级需求，DENY")
        decision = {"verdict":"DENY","winning_sigma":winner["sigma_id"],
                    "winning_protect_target":winner["protect_target"],
                    "reason":winner.get("reason","")}

    # ---- 4. (可选)用 Function B 找替代动作：服务 active 的安全需求且不违反更高需求 ----
    #    这里示范：若因 physical_security 否决了开窗，但仍有 personal_safety 的“降CO”需求 active，
    #    用 WDG 找“降 CO 且不制造入侵口”的替代。
    alt = None
    co_need = any("airborne" in e["sigma_id"] or "ventilation" in e["sigma_id"]
                  or "rising" in e["sigma_id"] for e in enriched)
    if decision["verdict"]=="DENY" and co_need:
        print(f"\n[4] 仍有空气危害类需求 active，用 Function B 在 WDG 找替代动作（降CO且不开外窗）：")
        try:
            cands = achieve_goal(wdg, "sensor.kitchen_co", "DECREASE", ws)
            # 过滤掉“开 cover/窗”类（那正是被否的），优先零副作用
            safe = [c for c in cands if "open_cover" not in c.action]
            for c in safe[:4]:
                se = ",".join(f"{e.target}:{e.effect}" for e in c.side_effects) or "无"
                print(f"     候选: {c.action}  (副作用: {se})")
            if safe:
                alt = safe[0].action
                print(f"   -> 选替代: {alt}（不开外窗，不制造入侵口）")
        except Exception as ex:
            print("     (Function B 不可用:", ex, ")")

    # ---- 5. DSL 表达 + grounding 成可复用规则 ----
    print(f"\n[5] DSL 处置 + grounded 可复用规则：")
    dsl = build_dsl(decision, pa, alt)
    print("   DSL plan:")
    for line in dsl: print("     " + line)
    rule = build_grounded_rule(decision, sit, alt, enriched, wdg)
    json.dump(rule, open("eval/grounded_rule_from_mediation.json","w"), indent=2, ensure_ascii=False)
    print("\n   已存 grounded 规则: eval/grounded_rule_from_mediation.json")
    return {"decision":decision,"dsl":dsl,"alternative":alt,"grounded_rule":rule}

def build_world_state(sit):
    """从 situation 的最后一帧 snapshot 还原 {entity: value}。"""
    sch = sit["device_schema"]; last = sit["snapshots"][-1]["states"]
    ws = {sch[i]: last[i] for i in range(len(sch))}
    # 给 WDG 用到的外部变量兜底
    ws.setdefault("sensor.outdoor_temperature", 15.0)
    ws.setdefault("sensor.outdoor_aqi", 30.0)
    # 名称对齐：situation 用 sensor.kitchen_co，WDG 也用，OK
    ws.setdefault("switch.main_power", "on")
    return ws

def build_dsl(decision, pa, alt):
    """用你的 DSL primitive 表达最终处置。"""
    target = pa["target"]; svc=pa["service"]
    if decision["verdict"]=="ALLOW":
        return [f"EXECUTE {svc}({target})"]
    plan = [f"DENY({svc}({target}))"]
    if alt:
        plan.append(f"EXECUTE {alt}()")
    plan.append('notify.silent(occupant, "proposed action withheld: violates a higher-priority requirement")')
    return ["["] + ["  "+p+"," for p in plan] + ["]"]

def build_grounded_rule(decision, sit, alt, enriched, wdg):
    """把这次裁决固化成一条带护栏、设备无关绑定、带优先级的可复用规则。"""
    winner = decision.get("winning_sigma")
    return {
        "rule_id": "grounded_"+(winner.split(".")[-1] if winner else "passthrough"),
        "synthesized_from_active_sigmas": [e["sigma_id"] for e in enriched],
        "winning_sigma": winner,
        "guard": {
            "comment": "护栏 = 胜出σ的纯situation激活前提，翻成真实信号；只在in-scene生效",
            "scene_predicate": "dwelling unattended/asleep (sleep_mode=on OR all persons not_home)"
        },
        "decision": decision["verdict"],
        "action_taken": ("DENY proposed_action" + (f" + EXECUTE {alt}" if alt else "")),
        "device_binding": {"intent_to_device_class": True,
                           "note": "换家庭重绑即可，不写死 entity"},
        "metadata": {"protect_target": decision.get("winning_protect_target","-"),
                     "priority_rank": PRIORITY.index(decision["winning_protect_target"])+1
                                      if decision.get("winning_protect_target") in PRIORITY else None,
                     "reusable": True}
    }

if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--activation", required=True, help="Stage1 输出的 JSON 文件")
    ap.add_argument("--situation", required=True)
    a=ap.parse_args()
    mediate(a.activation, a.situation)