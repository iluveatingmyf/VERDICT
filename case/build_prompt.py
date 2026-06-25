# ==============================================================================
# 功能: 自动化构建面向 LLM 评测的智能家居安全审计 Prompt (SYS + Few-shot + Lib + Sit)
# 调用: 
#   - 指定用例: python build_activation_prompt.py eval/situations/xxx.json
#   - 默认用例: python build_activation_prompt.py (自动使用 CO 注入攻击场景)
# 特性: 自动精简 16 条 Sigma 规则，并严格剥离 `_ground_truth` 答案字段以防数据泄漏
# 输出: 终端打印完整 Prompt，并在 eval/ 目录下同步存盘为同名 .txt 文件
# ==============================================================================

# -*- coding: utf-8 -*-
"""把 [系统指令 + few-shot + 完整16条σ库 + 一个situation] 拼成可直接粘到网页LLM的 prompt。
用法:
  python build_activation_prompt.py <situation.json>
  python build_activation_prompt.py                    # 默认注入攻击 situation
"""
import json, sys, os

LIB = "library/confirmed_properties.json"
DEFAULT_SIT = "eval/situations/situation_attack_co_inject.json"

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

SYS = """You are an advanced smart-home property mediator performing ACTIVATION JUDGEMENT. Your goal is to determine which formal security specifications (Sigmas) are currently triggered by a specific real-time incident.
### INPUTS AVAILABLE
1. SITUATION: A JSON containing `device_schema`, a chronological sequence of device `snapshots` (where differences between consecutive states constitute events), an `activity` field from a background sequence model, and the triggering automation rule (`trigger` and `proposed_action`).
2. SIGMA LIBRARY: A list of confirmed security specification fragments. Each contains an `activation` predicate, `signal_class`, `observable` status, `protect_target`, and `abstract_action`.
---
### EXECUTION PIPELINE
#### STEP 1 - Signal Reconstruction & Cause Coupling
Reconstruct the operational context into 6 dimensions. For the `activity` field, STRICTLY TRUST the provided situation value unless its confidence is low or label is idle/unknown.
*CRITICAL KEY TEST (Cause Coupling):* Analyze the state change of the variable that fired the trigger. Evaluate the relationship between the background `activity` and this physical telemetry change:
1. "explainable": The current activity naturally produces this telemetry change as a by-product (e.g., activity="cooking" perfectly explains a rising smoke/temperature reading).
2. "physical_hazard": The activity does not explain the reading (e.g., activity="sleeping"), BUT an active physical source/appliance capable of producing this effect is running in the snapshots.
3. "uncorroborated": The telemetry reading jumps abruptly with NO logical connection to the current activity AND NO supporting physical source in the home.
#### STEP 2 - Sigma Evaluation (Strict Matching)
For EVERY sigma in the library, output a verdict: `active` | `inactive` | `unknown` | `prompt_user`.
Apply these rules with absolute mathematical strictness to prevent over-activation:
- `active`: The `activation` predicate is logically and fully ENTAILED by your reconstructed signals from Step 1.
- `inactive`: The situation details or reconstructed signals explicitly contradict or do not satisfy the sigma's pre-conditions.
- `unknown`: The specific `signal_class` required by this sigma is COMPLETELY ABSENT or marked as unknown in the situation. (DO NOT hallucinate or guess values).
- `prompt_user`: The sigma's conditions match, but `observable` is explicitly marked as "no", meaning it requires human out-of-band verification.
*Mapping Guide:* Ensure that if a Sigma relies on `cause-evidence`, its activation verdict aligns seamlessly with your Step 1 Cause Coupling conclusion.
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
     "relied_on": ["..."], "confidence": 0.0, "reason": "..."}
  ],
  "active_set": ["sigma_id_1", "sigma_id_2"]
}"""

# few-shot：只示范最难的 STEP 1 cause-coupling 三分类，用中性的【浴室湿度】领域，
# 完全不碰 CO / 门锁 / 入侵，避免给测试题泄漏答案或诱导对齐。
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
    sit_path = sys.argv[1] if len(sys.argv)>1 else DEFAULT_SIT
    lib = json.load(open(LIB)); sit = json.load(open(sit_path))
    sit_clean = {k:v for k,v in sit.items() if k!="_ground_truth"}
    sigmas = compact_sigmas(lib)
    prompt = (SYS + "\n\n" + FEWSHOT
        + "\n\n===== SIGMA LIBRARY ("+str(len(sigmas))+" fragments) =====\n"
        + json.dumps(sigmas, indent=2, ensure_ascii=False)
        + "\n\n===== SITUATION =====\n"
        + json.dumps(sit_clean, indent=2, ensure_ascii=False)
        + "\n\nNow perform STEP 1-3 and output the JSON only.")
    base = os.path.splitext(os.path.basename(sit_path))[0]
    outp = f"eval/activation_prompt_{base}.txt"
    open(outp,"w").write(prompt)
    print(prompt)
    print("\n\n[stored:", outp, "| chars:", len(prompt), "]")
    if "_ground_truth" in sit:
        print("[GROUND TRUTH (NOT in prompt, for your own check):", sit["_ground_truth"]["should_activate"], "]")

if __name__ == "__main__":
    main()