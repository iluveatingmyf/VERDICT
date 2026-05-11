       ┌─────────────────────────────────────────────────┐
       │  Trigger event + Π₀ + World state               │
       └────────────────────┬────────────────────────────┘
                            │
       ┌────────────────────▼────────────────────────────┐
       │  [SYMBOLIC] Cascade Graph Builder               │  ← 代码分析 #1
       │  Static reachability over automation rules      │
       │  Output: G_c = full cascade DAG                 │
       └────────────────────┬────────────────────────────┘
                            │
   ┌────────────────────────┼────────────────────────────┐
   │                        │                            │
   ▼                        ▼                            ▼
┌────────────┐  ┌────────────────────┐  ┌──────────────────────┐
│ Agent A:   │  │ Agent B:           │  │ Agent C:             │
│ Intent     │  │ Risk Assessor      │  │ Plan Synthesizer     │
│ Inference  │  │ (per-step          │  │ (DSL plan,           │
│ → I_spec   │  │ impact tagging on  │  │ principles applied)  │
│            │  │ G_c against I_spec)│  │                      │
└─────┬──────┘  └─────────┬──────────┘  └──────────┬───────────┘
      │                   │                        │
      └───────────────────┴────────────────────────┘
                            │
                            ▼
                ┌─────────────────────────┐
                │ Agent D: Adversarial    │  ← 红队 agent
                │ Verifier (red team)     │
                │ Tries to break the plan │
                └────────────┬────────────┘
                             │
       ┌─────────────────────▼────────────────────┐
       │  [SYMBOLIC] Plan Validator              │  ← 代码分析 #2
       │  - DSL parse + type check               │
       │  - Capability check vs WDG              │
       │  - LTL constraint check on plan         │
       │  - Differential check: LLM cascade      │
       │    prediction vs static G_c             │
       └─────────────────────┬───────────────────┘
                             │
                             ▼
                    VERIFIED PLAN  /  REJECT