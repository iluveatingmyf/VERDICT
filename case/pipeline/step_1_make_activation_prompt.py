# -*- coding: utf-8 -*-
"""把 [系统指令 + few-shot + 完整16条σ库 + 一个situation] 拼成可直接粘到网页LLM的 prompt。
用法:
  python build_activation_prompt.py <4位ID> (例如: 5565, 2671)
"""
import json
import sys
import os
import glob

# 采用第二个脚本的指定 LIB 路径
LIB = "../properties/confirmed_properties.json"

def compact_sigmas(lib):
    out=[]
    for s in lib["sigmas"]:
        out.append({
            "sigma_id": s["sigma_id"], "from_property": s["from_property"],
            "activation": s["activation"], "signal_class": s["signal_class"],
            "observable": s["observable"], "protect_target": s["protect_target"],
            "abstract_action": s["abstract_action"],
        })
    return out

# 保留了第一个脚本中逻辑更严谨、区分了 Standing / Event 模态的完整 SYS 提示词
SYS = """You are an advanced smart-home property mediator performing ACTIVATION JUDGEMENT. Your goal is to determine which formal security specifications (Sigmas) are currently triggered by a specific real-time incident.
### INPUTS AVAILABLE
1. SITUATION: A JSON containing `device_schema`, a chronological sequence of device `snapshots` (where differences between consecutive states constitute events), an `activity` field from a background sequence model, and the triggering automation rule (`trigger` and `proposed_action`).
2. SIGMA LIBRARY: A list of confirmed security specification fragments. Each contains an `activation` predicate, `signal_class`, `observable` status, `protect_target`, and `abstract_action`.
---
### EXECUTION PIPELINE
#### STEP 1 - Signal Reconstruction & Cause Coupling
Reconstruct the operational context into 6 dimensions. For the `activity` field, STRICTLY TRUST the provided situation value unless its confidence is low or label is idle/unknown.
*CRITICAL KEY TEST (Cause Coupling):* Analyze the state change of the variable that fired the trigger. Evaluate the relationship between the background `activity` and this physical telemetry change:
1. "explainable": The current activity naturally produces this telemetry change as a by-product (i.e., the ongoing activity is itself a known cause of this kind of reading rising).
2. "physical_hazard": The activity does not explain the reading, BUT an active physical source/appliance capable of producing this effect is present/running in the snapshots.
3. "uncorroborated": The telemetry reading jumps abruptly with NO logical connection to the current activity AND NO supporting physical source in the home.
#### STEP 2 - Two-Stage Sigma Evaluation
A sigma's `activation` is a PURE-SITUATION requirement: it states what must be upheld GIVEN THE SITUATION ALONE. It does NOT mention the proposed_action. Evaluate in two stages.

STAGE 2A - Requirement activation (situation only, IGNORE proposed_action):
For EVERY sigma, decide whether its situational requirement is RAISED by the reconstructed signals:
- `active` (requirement raised): the situational precondition in `activation` is ENTAILED by Step-1 signals. Do NOT restrict activation to sigmas related to the trigger — judge every sigma against the situation on its own terms.
  CRITICAL distinction — is the `activation` a STANDING REQUIREMENT or an EVENT PREDICATE?
   * A STANDING REQUIREMENT mandates that some state be MAINTAINED while a situation holds (it describes the goal to keep, not an event that happened). Its activation is decided SOLELY by whether its situational precondition holds (e.g. an occupancy/time/presence condition). Whether the world CURRENTLY already satisfies the maintained state is IRRELEVANT to activation: a "keep X while S" requirement is `active` whenever S holds, EVEN IF X is currently satisfied — because its job is to prevent X from being broken. Never judge such a sigma `inactive` on the grounds that "nothing is currently violated" or "things currently look fine"; current compliance is checked later in 2B, not here.
   * An EVENT PREDICATE describes a specific occurrence that must be present in the signals to fire. It is `active` only if that occurrence is entailed.
   Read each sigma's `activation` to decide which kind it is, then apply the matching test.
- `inactive`: the situation does not raise this requirement (its situational precondition is contradicted/absent).
- `unknown`: the needed `signal_class` is ABSENT or unmeasured in the situation. Do NOT infer it from unrelated readings, do NOT assume a default, do NOT reason "probably X" — absence of the required signal means `unknown`, full stop. (e.g. if no outdoor-air data exists, any sigma needing outdoor comparison is `unknown`, not active/inactive.)
- `prompt_user`: matches but `observable`=="no".
*Mapping Guide:* a sigma relying on `cause-evidence` must align with the Step-1 cause-coupling verdict.

STAGE 2B - Compliance check (now bring in proposed_action):
For each sigma marked `active` in 2A, additionally assess whether the SITUATION's `proposed_action`, if executed, would VIOLATE that raised requirement. Derive the action's effect simply (e.g. an open-cover service call results in that cover/opening becoming OPEN). Report this as a separate field `violated_by_proposed_action`: true/false, with the effect you derived. (This does NOT change the 2A verdict; it tells the downstream mediator which active requirements the action breaks.)
#### STEP 3 - Justification
For each evaluated sigma, provide the verdict, a list of specific signals relied upon, a confidence score (0.0 to 1.0), and a concise, one-line logical deduction.
---
### OUTPUT FORMAT
Output the results in raw JSON format ONLY. Ensure no markdown formatting errors.
{
  "reconstructed_signals": {
    "time": "...", "occupancy": "...", "activity": "...",
    "trajectory": "...", "cause_evidence": "...", "external_alarm": "..."
  },
  "cause_coupling_verdict": "explainable | physical_hazard | uncorroborated",
  "activations": [
    {"sigma_id": "...", "verdict": "active | inactive | unknown | prompt_user",
     "relied_on": ["..."], "confidence": 0.0,
     "violated_by_proposed_action": false, "violation_effect": "...",
     "reason": "..."}
  ],
  "active_set": ["sigma_id_1", "sigma_id_2"]
}"""

FEWSHOT = """---
### CALIBRATION EXAMPLE (illustrates ONLY the Step-1 cause-coupling judgement; an unrelated domain, not part of the test)

Trigger fired: bathroom_humidity crossed a high threshold. Three different situations, same trigger:

(a) activity="showering" (confidence 0.9); snapshots show shower running, humidity climbing steadily during the shower.
    -> cause_coupling = "explainable": the ongoing activity naturally produces rising humidity as a by-product.

(b) activity="sleeping" (humidity unrelated to it), BUT a water-leak sensor reads wet and humidity climbs.
    -> cause_coupling = "physical_hazard": activity does not explain it, but a real physical source (leak) is present.

(c) activity="idle"; humidity value jumps abruptly from 40 to 85 in one snapshot, no shower, no leak sensor, no water source active.
    -> cause_coupling = "uncorroborated": neither the activity nor any physical source accounts for the jump.

Apply this same three-way reasoning to the trigger variable in the real SITUATION below. The domain there will differ; the reasoning is identical.
"""

def main():
    if len(sys.argv) < 2:
        print("错误: 请输入4位ID。例如: python build_activation_prompt.py 5565")
        sys.exit(1)

    # 获取终端输入的4位ID
    id_suffix = sys.argv[1]

    # 采用第二个脚本的指定模糊匹配路径
    search_pattern = f"../eval/situations/generated/*_{id_suffix}.json"
    matched_files = glob.glob(search_pattern)

    if not matched_files:
        print(f"错误: 未找到以 '_{id_suffix}.json' 结尾的 situation 文件！")
        sys.exit(1)

    # 默认取第一个匹配到的文件
    sit_path = matched_files[0]
    print(f"[找到文件]: {sit_path}")

    # 读取文件
    lib = json.load(open(LIB))
    sit = json.load(open(sit_path))
    
    # 数据清洗与压缩
    sit_clean = {k:v for k,v in sit.items() if k!="_ground_truth"}
    sigmas = compact_sigmas(lib)
    
    # 组装 Prompt
    prompt = (SYS + "\n\n" + FEWSHOT
        + "\n\n===== SIGMA LIBRARY ("+str(len(sigmas))+" fragments) =====\n"
        + json.dumps(sigmas, indent=2, ensure_ascii=False)
        + "\n\n===== SITUATION =====\n"
        + json.dumps(sit_clean, indent=2, ensure_ascii=False)
        + "\n\nNow perform STEP 1-3 and output the JSON only.")
    
    # 采用第二个脚本的动态路径创建逻辑：case/cacase/{4位ID}/
    output_dir = f"./case/cacase/{id_suffix}"
    os.makedirs(output_dir, exist_ok=True)
    
    # 写入文件
    base = os.path.splitext(os.path.basename(sit_path))[0]
    outp = f"{output_dir}/activation_prompt_{base}.txt"
    open(outp, "w").write(prompt)
    
    # 打印终端反馈
    print(prompt)
    print(f"\n\n[stored: {outp} | chars: {len(prompt)}]")
    if "_ground_truth" in sit:
        print("[GROUND TRUTH (NOT in prompt, for your own check):", sit["_ground_truth"]["should_activate"], "]")

if __name__ == "__main__":
    main()