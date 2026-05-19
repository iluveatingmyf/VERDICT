LLM-as-runtime-monitor 在现实部署中有四类 cost，每一类 reviewer 都会问，必须有数据回答：
1. Latency：Gemini 2.5 Pro 单次调用 2-5 秒，3-agent pipeline = 6-15 秒。对很多 IoT 触发（motion → light）这个延迟完全不可接受。

你的 RQ4 已经包含 overhead 分析，必须把这个数据漂亮地呈现出来
一个 mitigation：fast path / slow path 架构——大部分 rule firing 直接 ALLOW（fast path），只有当 cascade analyzer 检测到 chain ≥ 2 或 conflict 时才走 LLM（slow path）。论文里把这个工程决策讲清楚，cost 问题就化解了一半

2. Money：约 $0.02-0.05 per mediation × 几十次/天 = 月成本几十美元/户。对消费 IoT 过高。

Mitigation 1：本地小模型（Llama 3.1 8B / Qwen 2.5 7B）跑前两个 agent，只有最关键的 Plan Synthesizer 用 cloud LLM
Mitigation 2：cache mediation decisions（相同 situation → 复用之前的 plan）
你可以做一个轻量 ablation：full Gemini vs hybrid (local small + cloud large)，证明 hybrid 在保持精度同时大幅降本

3. Cloud dependency / privacy：把所有 sensor stream 送到 Google，这本身是个隐私问题——讽刺的是你的论文在讲安全。reviewer 100% 会问。

必须在 limitations 一节坦诚承认
提一句 "edge-deployable LLMs (Llama 3.2 1B/3B running on-device) are an active research direction that addresses this concern in future work"

4. Non-determinism：LLM 输出不稳定，相同 input 可能不同 plan。这对 security 系统是大问题。

你用 temperature=0 是对的（PDF 里看到了）
必须 report：相同 scenario 跑 N 次的 plan consistency rate