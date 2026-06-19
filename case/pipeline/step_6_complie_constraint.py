# -*- coding: utf-8 -*-
"""第6步【代码】：把裁决的 reusable_constraint 固化成纯设备状态policy，并入库(去重/冲突)。
B方案：筛选(reusable) → 锁稳定特征 → WDG展开动作类 → 与已有policy库代码级去重/冲突。
用法: python step6_compile_constraint.py <sid>
固化后 runtime 直接查 policy 库，匹配 WHEN 即套用 verdict，不再调 LLM。"""
import json
import os
import sys
from pathlib import Path
import glob

# ==================== 1. 自动路径定位与导入修复 ====================
# 获取当前脚本的绝对路径 (/[...]/VERDICT/case/pipeline/step3_wdg_facts.py)
current_file = Path(__file__).resolve()

# 核心定位：
# pipeline_dir = .../VERDICT/case/pipeline
# case_dir     = .../VERDICT/case
# root_dir     = .../VERDICT  (这里包含了 core 和 case)
pipeline_dir = current_file.parent
case_dir = pipeline_dir.parent
root_dir = case_dir.parent

# 将 VERDICT 根目录加入系统路径，确保 core.simulator 导入成功
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

# 打印调试信息，方便核对
print(f"[Debug] 成功加入项目根目录: {root_dir}")

from core.simulator import load_wdg

PRIORITY=["personal_safety","physical_security","privacy","task_completion","comfort","energy"]
POLICY_DB="./policies/compiled_policies.json"   # 增长的可复用policy库

def load_db():
    if os.path.exists(POLICY_DB):
        return json.load(open(POLICY_DB))
    return {"_meta":{"desc":"compiled pure-device-state policies; runtime lookup, no LLM"},"policies":[]}

# --- 语义"情景前提" -> 可观测设备状态谓词（static + dynamic）---
def expand_situation(text):
    t=text.lower(); static=[]; dynamic=[]
    if any(k in t for k in ["unattended","asleep","sleep","unguarded","non-vigilant"]):
        static.append({"any_of":[{"entity":"input_select.sleep_mode","op":"==","value":"on"},
                                 {"all_persons":"not_home"}]})
    if any(k in t for k in ["away","not at home","not nearby","departed","vacation","extended-absence"]):
        static.append({"all_persons":"not_home"})
    # dynamic：若情景前提里点到"成因可疑/突变"，锁一个cause语义标签(由step3的符号判定给，不调LLM)
    if any(k in t for k in ["uncorroborated","spurious","abrupt","sudden"]):
        dynamic.append({"cause_coupling":"uncorroborated"})
    return static, dynamic

# --- target_device_class token -> WDG设备清单（纯查表，不猜语义）---
# token -> (匹配函数, 该类的目标状态语义)
TOKEN_MAP = {
    "access_channel":     (lambda n: n.get("class") in ("cover","lock"), "open_or_unlock"),
    "powered_ventilation":(lambda n: "ventilation" in n.get("capabilities",[]) and n.get("class") not in ("cover",), "on"),
    "outdoor_air_exchange":(lambda n: "outdoor_air_exchange" in n.get("capabilities",[]), "open"),
    "air_purification":   (lambda n: "air_purification" in n.get("capabilities",[]), "on"),
    "illumination":       (lambda n: "illumination" in n.get("capabilities",[]), "on"),
    "thermal":            (lambda n: n.get("class")=="climate" or "heating" in n.get("capabilities",[]) or "cooling" in n.get("capabilities",[]), "on"),
    "alarming":           (lambda n: "alarming" in n.get("capabilities",[]) or n.get("class")=="alarm_control_panel", "trigger"),
    "access_control":     (lambda n: n.get("class")=="lock", "lock"),
    "power_gating":       (lambda n: "power_gating" in n.get("capabilities",[]), "off"),
    "surveillance":       (lambda n: "surveillance" in n.get("capabilities",[]) or n.get("class")=="camera", "on"),
}
def expand_action_class(tokens, wdg):
    """tokens: LLM在verdict里给的 target_device_class 列表（固定token）。纯查表。"""
    if isinstance(tokens, str): tokens=[tokens]
    devices=[]; states=set()
    for tok in (tokens or []):
        if tok not in TOKEN_MAP:
            continue  # 未知token跳过（LLM该只用固定表）
        match_fn, state = TOKEN_MAP[tok]
        for n in wdg.nodes.values():
            if match_fn(n): devices.append({"entity":n["id"],"to_state":state,"via_token":tok})
        states.add(state)
    # 去重
    seen=set(); uniq=[]
    for d in devices:
        k=(d["entity"],d["to_state"])
        if k not in seen: seen.add(k); uniq.append(d)
    return uniq

# --- 代码级去重/冲突检查 ---
def when_key(static, dynamic):
    """把WHEN规范化成可比较的key（排序后的谓词集合）。"""
    return json.dumps({"s":sorted(map(json.dumps,static)),"d":sorted(map(json.dumps,dynamic))},sort_keys=True)

def reconcile(db, new_pol):
    nk=when_key(new_pol["WHEN_static"],new_pol["WHEN_dynamic"])
    for p in db["policies"]:
        ek=when_key(p["WHEN_static"],p["WHEN_dynamic"])
        if ek==nk:
            # WHEN 完全相同
            if p["verdict"]==new_pol["verdict"] and p["forbid_or_require"]==new_pol["forbid_or_require"]:
                # 重复 -> 合并设备清单
                before=set(map(json.dumps,p["targets"]))
                p["targets"]=[json.loads(x) for x in before|set(map(json.dumps,new_pol["targets"]))]
                p.setdefault("merged_from",[]).append(new_pol["constraint_id"])
                return "merged_duplicate", p["constraint_id"]
            else:
                # WHEN同但裁决冲突 -> 标记待裁决，不静默覆盖
                db.setdefault("_conflicts",[]).append(
                    {"existing":p["constraint_id"],"incoming":new_pol["constraint_id"],
                     "same_WHEN":True,"verdict_existing":p["verdict"],"verdict_incoming":new_pol["verdict"]})
                return "CONFLICT_flagged", p["constraint_id"]
    db["policies"].append(new_pol)
    return "added_new", new_pol["constraint_id"]

def main():
    sid=sys.argv[1]; base=f"./case/cacase/{sid}"
    if not os.path.exists(f"{base}/05_verdict_result.json"):
        base=f"./case/cacase/{sid}"
    v=json.load(open(f"{base}/05_verdict_result.json"))
    wdg=load_wdg("../../data/wdg.json")
    rc=v.get("reusable_constraint",{})

    # B方案第一步：筛选
    if not rc.get("reusable", False):
        out={"constraint_id":f"c_{sid}","reusable":False,
             "reuse_basis":rc.get("reuse_basis","(verdict marked non-reusable)"),
             "note":"未通过复用筛选，不入policy库（可能是一次性/依赖存疑信号/特征不稳定）。"}
        json.dump(out,open(f"{base}/06_reusable_constraint.json","w"),indent=2,ensure_ascii=False)
        print(f"[SKIP] {sid} reusable=false：{out['reuse_basis'][:80]}")
        return

    static,dynamic=expand_situation(rc.get("when_situation",""))
    targets=expand_action_class(rc.get("target_device_class", rc.get("action_class","")), wdg)
    new_pol={
      "constraint_id":f"c_{sid}",
      "source_verdict":{"winning":v.get("winning_requirement"),"verdict":v.get("verdict")},
      "WHEN_static":static,"WHEN_dynamic":dynamic,
      "forbid_or_require":rc.get("forbid_or_require","FORBID"),
      "targets":targets,
      "verdict":v.get("verdict"),
      "protect_target":rc.get("protect_target"),
      "priority_rank":(PRIORITY.index(rc["protect_target"])+1) if rc.get("protect_target") in PRIORITY else None,
      "reuse_basis":rc.get("reuse_basis",""),
      "pure_device_state":True,"reusable_without_llm":True
    }
    # 单条产物
    json.dump(new_pol,open(f"{base}/06_reusable_constraint.json","w"),indent=2,ensure_ascii=False)
    # 入库 + 去重/冲突
    db=load_db(); status,cid=reconcile(db,new_pol)
    json.dump(db,open(POLICY_DB,"w"),indent=2,ensure_ascii=False)
    print(f"[OK] {base}/06_reusable_constraint.json")
    print(f"  入库结果: {status}  (针对 {cid})")
    print(f"  WHEN_static: {json.dumps(static,ensure_ascii=False)}")
    print(f"  WHEN_dynamic: {json.dumps(dynamic,ensure_ascii=False)}")
    print(f"  {new_pol['forbid_or_require']} {len(new_pol['targets'])} 设备: " + str([t['entity']+'@'+t['to_state'] for t in new_pol['targets'][:6]]))
    print(f"  policy库现有 {len(db['policies'])} 条" + (f" | ⚠️冲突 {len(db['_conflicts'])} 处" if db.get('_conflicts') else ""))

if __name__=="__main__":
    main()