# -*- coding: utf-8 -*-
"""第3步【代码】：用WDG(Function A/B)算 提议动作的后果 + 候选替代动作。
用法: python step3_wdg_facts.py <4位数字sid>"""
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

from core.simulator import load_wdg, forward_simulate, achieve_goal
# ==================================================================

SERVICE_RESULT={"cover.open_cover":"open","cover.close_cover":"closed","lock.lock":"locked",
    "lock.unlock":"unlocked","fan.turn_on":"on","switch.turn_on":"on","light.turn_on":"on"}

def world_state(sit):
    sch=sit["device_schema"]; last=sit["snapshots"][-1]["states"]
    ws={sch[i]:last[i] for i in range(len(sch))}
    ws.setdefault("sensor.outdoor_temperature",15.0); ws.setdefault("sensor.outdoor_aqi",30.0)
    ws.setdefault("switch.main_power","on")
    return ws

def ser_trace(steps):
    return [{"hop":s.hop,"effects":[{"target":e.target,"effect":e.effect,
            "via":e.via_edge_id} for e in s.effects]} for s in steps]

# ==================== 2. 四位数字 SID 模糊匹配逻辑 ====================
input_sid = sys.argv[1]

# 构建 eval 文件夹的绝对路径，避免由于在不同目录下执行导致相对路径失效
eval_dir = case_dir / "eval" / "situations" / "generated"

# 寻找带有该四位数字的 JSON 文件
search_pattern = str(eval_dir / f"*{input_sid}.json")
matched_files = glob.glob(search_pattern)

if not matched_files:
    print(f"[Error] 未能在 {eval_dir} 中找到包含数字 {input_sid} 的 JSON 文件！")
    sys.exit(1)

# 获取匹配到的第一个文件的绝对路径，并提取出它的文件名（作为后续 runs 的目录名）
target_file_path = matched_files[0]
sid = Path(target_file_path).stem  # 例如: sit_co_spurious_sleeping_deep_night_2671
print(f"[找到文件]: {target_file_path}")
# ==================================================================

sit=json.load(open(target_file_path))
# 同样将 data/wdg.json 改为基于 case_dir 的绝对路径，防止找不到文件
wdg=load_wdg(str("/Users/myf/VERDICT/data/wdg.json"))
pa=sit["proposed_action"]; ws=world_state(sit)

# A. 提议动作的后果
ns=SERVICE_RESULT.get(pa["service"],"fired"); ws2=dict(ws); ws2[pa["target"]]=ns
delta=forward_simulate(wdg,{"node":pa["target"],"event":{"kind":"state","to":ns}},ws2)

# B. 候选替代：若trigger是CO，找“降CO”的动作（通用：按trigger的传感器找reduce方向）
alternatives=[]
trig_entity=sit["trigger"]["entity"]
# 把 situation 的 sensor.kitchen_co 对到 WDG 同名节点
if wdg.node(trig_entity):
    try:
        cands=achieve_goal(wdg, trig_entity, "DECREASE", ws)
        for c in cands:
            alternatives.append({"action":c.action,"via":c.via_capability,
                "side_effects":[{"target":e.target,"effect":e.effect} for e in c.side_effects]})
    except Exception as ex:
        alternatives=[{"error":str(ex)}]

facts={"proposed_action":pa,
       "delta_of_proposed_action":ser_trace(delta),
       "alternatives_for_trigger_goal":alternatives,
       "note":"delta=提议动作的真实后果链(Function A);alternatives=能让触发变量反向的候选动作+副作用(Function B)。均为WDG符号推演,非LLM。"}

# 同样将输出的 runs 目录基于 case_dir 定位
# ==================== 修复后的输出路径逻辑 ====================
# 1. 确保拿到的是纯数字（比如 2671）
folder_name = input_sid 

# 2. 正确拼接目录路径（把目标指向真正的 cacase/{数字} 文件夹）
target_dir = case_dir / "pipeline" / "case" / "cacase" / folder_name

# 3. 自动创建这个数字文件夹（如果不存在的话）
os.makedirs(target_dir, exist_ok=True)

# 4. 最终的文件绝对路径
output_file = target_dir / "03_wdg_facts.json"

# 5. 写入 JSON
json.dump(facts, open(output_file, "w"), indent=2, ensure_ascii=False)

# 6. 打印干净漂亮的日志
print(f"[OK] 文件已成功输出至: {output_file}")
# ============================================================