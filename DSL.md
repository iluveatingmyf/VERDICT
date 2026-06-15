## Part 1: VERDICT 的 Plan DSL 完整总结

### 1.1 DSL 的设计原则

3 条:

1. **Minimal primitive set**: 4 个 
2. **Compositional**: primitive 可以嵌套 (e.g., `DELAY(5m) DENY(action)`)
3. **Symbolically validatable**: 任何 plan 可被 LTL validator 静态检查

### 1.2 完整 primitive 清单

| Primitive | Syntax | Semantics | 主要服务的 AP |
|---|---|---|---|
| **EXECUTE** | `service.call(entity_id, {params})` | 立即执行 service call | 通用 (ALLOW path) |
| **DENY** | `DENY(action)` | 永久阻止此 trigger instance 的 action | 通用 (所有 AP 的 hard rejection) |
| **ADAPT** | `ADAPT(action with {new_params})` | 用修改后的参数执行 | AP2-a (timer override 合并) |
| **AFTER** | `AFTER(condition) action` | 等条件满足后执行 | AP2-c, AP6 |
| **DELAY** | `DELAY(duration) action` | 固定延迟后执行 | AP2-a, emergency hold |

加上 2 个**复合 primitive** (由 plan synthesizer 组装):

| Primitive | Syntax | Semantics |
|---|---|---|
| **PARALLEL** | `[action_1; action_2; ...]` | 并发执行多个 action |
| **SEQUENCE** | `[action_1 → action_2 → ...]` | 顺序执行（前一个完成后才下一个） |

### 1.3 Condition grammar (AFTER 的 argument)

`AFTER(condition)` 的 condition **严格限制**为以下三种 (避免 LLM 自由发挥):

```
condition ::= entity_state_predicate
            | duration_elapsed
            | conjunction(c1, c2)

entity_state_predicate ::= entity_id operator value
operator ::= == | != | < | > | <= | >=
value ::= literal | 'state_name'

duration_elapsed ::= duration_since(entity_id, state, duration)
```

例:
- ✅ `AFTER(binary_sensor.living_room_motion == 'off')` 
- ✅ `AFTER(duration_since(binary_sensor.living_room_motion, 'off', '5m'))`
- ✅ `AFTER(conjunction(sensor.temperature > 20, sensor.smoke == 'off'))`
- ❌ `AFTER(activity_change)` ← 之前 Janus 允许这个，新版 forbidden (太 vague)
- ❌ `AFTER(user_intent_shifted)` ← 同上 forbidden

**为什么严格**: condition 必须**完全 sensor/state grounded**——这样 plan validator 可以静态检查 "这个 AFTER 会不会永远 unfulfilled"。

### 1.4 Duration grammar

```
duration ::= integer ('s' | 'm' | 'h' | 'd')
```

例: `30s`, `5m`, `2h`, `1d`

### 1.5 完整 BNF

```
plan ::= action_list

action_list ::= action | action_list ; action

action ::= execute | deny | adapt | after | delay | parallel | sequence

execute ::= service '.' method '(' entity_id ',' params ')'
deny ::= 'DENY' '(' action ')'
adapt ::= 'ADAPT' '(' action ')'    # 包含修改后的 params
after ::= 'AFTER' '(' condition ')' action
delay ::= 'DELAY' '(' duration ')' action
parallel ::= '[' action_list ']'    # 并发分组
sequence ::= action '→' action      # 顺序

# (condition / duration grammar 同上)
```

### 1.6 Plan 例子 (跨 AP 收集)

```
# AP1: Single rule reject
[DENY(lock.unlock(front_door))]

# AP2-a: Timer override 合并
[ADAPT(fan.ventilation_fan.turn_on({for: '15m'}))]

# AP2-c: Cascade fine-grained mediation  
[
  fan.bathroom_fan.turn_on(),
  DENY(light.bathroom_light.turn_off),
  AFTER(binary_sensor.bathroom_motion == 'off') 
    DELAY(5m) light.bathroom_light.turn_off()
]

# AP4: Spoofing detection + silent alert
[
  DENY(cover.kitchen_window.open),
  notify.silent(occupant_phone, 'sensor anomaly')
]

# AP6: TOCTOU re-validation (handled by validator at execution time, 
#      plan 不显式表达)

# AP7: Emergency fire response
[
  DENY(cover.kitchen_window.open),
  lock.unlock(front_door),
  lock.unlock(back_door),
  alarm_control_panel.alarm_trigger(fire),
  notify.audible(all_occupants, EMERGENCY)
]
```

---

## Part 2: DSL 用什么语言"定义"——四个 layer

这里有个**容易混淆**的点: DSL 的**定义**和 DSL 的**实现**是不同 layer。让我分清楚:

### Layer 1: Syntactic Definition (语法层)

**用什么**: BNF / EBNF (Extended Backus-Naur Form)

**Paper 里展示**: 上面 1.5 节那种 BNF grammar

**实现**: 用 `lark` (Python parsing library) 或 `pyparsing` 实现 parser

```python
# Using lark
from lark import Lark

VERDICT_DSL_GRAMMAR = """
    plan: action_list
    action_list: action (";" action)*
    action: execute | deny | adapt | after | delay
    execute: service "." method "(" entity_id "," params ")"
    deny: "DENY" "(" action ")"
    adapt: "ADAPT" "(" action ")"
    after: "AFTER" "(" condition ")" action
    delay: "DELAY" "(" duration ")" action
    # ...
"""

parser = Lark(VERDICT_DSL_GRAMMAR, start='plan')
```

### Layer 2: Type System (类型层)

**用什么**: Python dataclass + Enum (轻量) 或 attrs (中量) 或 Pydantic (重量)

**Paper 里展示**: dataclass 定义

```python
from dataclasses import dataclass
from typing import Union, List, Optional
from enum import Enum

class PrimitiveType(Enum):
    EXECUTE = "execute"
    DENY = "deny"
    ADAPT = "adapt"
    AFTER = "after"
    DELAY = "delay"

@dataclass
class ServiceCall:
    domain: str          # e.g., "light", "lock", "fan"
    service: str         # e.g., "turn_on", "unlock"
    entity_id: str
    data: dict           # parameters

@dataclass
class Condition:
    entity_id: str
    operator: str        # ==, !=, <, > etc
    value: str           # state value

@dataclass
class Action:
    primitive: PrimitiveType
    target: Optional[ServiceCall] = None        # for EXECUTE, ADAPT
    condition: Optional[Condition] = None       # for AFTER
    duration: Optional[str] = None              # for DELAY
    nested: Optional['Action'] = None           # for DENY, ADAPT, AFTER, DELAY (compound)

@dataclass
class Plan:
    actions: List[Action]
```

### Layer 3: Operational Semantics (运行语义)

**用什么**: 描述每个 primitive 如何被 executor 解释执行——用**自然语言 + state transition rules**

**Paper 里展示**: 一张语义表 + 几条 transition rule

例 (paper section 形式):

> **Semantics of EXECUTE**: Given action `service.call(entity, params)` at time $t$, the executor dispatches `HA.call_service(domain, service, entity, params)` at $t$.
>
> **Semantics of AFTER**: Given action `AFTER(c) a`, the executor registers a state listener for condition $c$. When $c$ becomes True at time $t' \geq t$, executor evaluates semantics of $a$ at $t'$. If $c$ never becomes True within session timeout $T_{max}$, action is dropped.
>
> **Semantics of DENY**: Given `DENY(a)`, executor marks action $a$ as blocked. If automation rule attempts to dispatch $a$ within this mediation cycle, the dispatch is suppressed at the executor level (not the rule engine level).

### Layer 4: Translation to HomeAssistant (实现层)

这是你的下一个问题 — Part 3 详细讲。

### 总结 paper 里怎么写 DSL definition

Paper §4.X (Plan DSL) 里包含 4 个 subsection:

1. **§4.X.1 Design Rationale**: 为什么 4+2 primitive, 跟 ContexIoT binary 对比
2. **§4.X.2 Syntax**: BNF grammar (1/4 页)
3. **§4.X.3 Type System**: dataclass definitions
4. **§4.X.4 Operational Semantics**: 每个 primitive 的执行语义

总长 **1-1.5 页**。

---

## Part 3: 通过 MCP 转化为 HomeAssistant Service Call

### 3.1 整体翻译 pipeline

```
VERDICT Plan (内部 DSL)
   ↓ [Translator]
HA-compatible action sequence
   ↓ [MCP Server]
HomeAssistant REST API / WebSocket
   ↓
Actual device actions
```

### 3.2 MCP 在哪里发挥作用

**MCP (Model Context Protocol)** 是 Anthropic 的标准 protocol，让 LLM 和 external service 之间结构化通信。在 VERDICT 里 MCP 的角色：

**MCP 用作 VERDICT ↔ HomeAssistant 的标准化接口**:

```
VERDICT runtime
   │
   │  (calls MCP tools)
   ↓
MCP Server (custom-built)
   │
   │  (translates to HA API)
   ↓  
HomeAssistant
```

MCP Server 暴露的 tools:
- `ha.call_service(domain, service, entity_id, data)` → 直接 service call
- `ha.get_state(entity_id)` → 查 entity 当前 state (for condition evaluation)
- `ha.subscribe_state(entity_id, callback)` → 监听 state 变化 (for AFTER)
- `ha.get_entity_metadata(entity_id)` → 查 entity capabilities

### 3.3 Primitive 到 HA service call 的具体 translation 表

这是**核心 deliverable**:

| VERDICT DSL | HA service call sequence | MCP tool used |
|---|---|---|
| `light.turn_off(light.bathroom, {})` | `POST /api/services/light/turn_off {"entity_id": "light.bathroom"}` | `ha.call_service` |
| `DENY(light.turn_off(...))` | **No HA call** (executor suppresses) | (none) |
| `DELAY(5m) action` | `setTimeout(5min) then translate(action)` | `ha.call_service` after delay |
| `AFTER(entity==value) action` | Register state listener, on match translate(action) | `ha.subscribe_state` + `ha.call_service` |
| `ADAPT(action with new_params)` | Same as `service.call` but with adapted params | `ha.call_service` (with new data) |
| `[a1; a2]` (parallel) | Multiple parallel calls | Multiple `ha.call_service` calls |

### 3.4 完整 worked example

**VERDICT plan** (你 S2.11 的 final mediated plan):
```
[
  fan.bathroom_fan.turn_on(),
  DENY(light.bathroom_light.turn_off),
  AFTER(binary_sensor.bathroom_motion == 'off') 
    DELAY(5m) light.bathroom_light.turn_off()
]
```

**Translation algorithm**:

```python
def translate_plan_to_ha(plan: Plan, mcp_client) -> List[HAOperation]:
    operations = []
    for action in plan.actions:
        operations.extend(translate_action(action, mcp_client))
    return operations

def translate_action(action: Action, mcp_client) -> List[HAOperation]:
    if action.primitive == PrimitiveType.EXECUTE:
        return [HACallService(
            domain=action.target.domain,
            service=action.target.service,
            entity_id=action.target.entity_id,
            data=action.target.data
        )]
    
    elif action.primitive == PrimitiveType.DENY:
        return [HASuppress(action.nested)]  # no actual HA call
    
    elif action.primitive == PrimitiveType.DELAY:
        return [HAScheduledCall(
            delay=action.duration,
            inner=translate_action(action.nested, mcp_client)
        )]
    
    elif action.primitive == PrimitiveType.AFTER:
        return [HAStateListener(
            entity_id=action.condition.entity_id,
            operator=action.condition.operator,
            value=action.condition.value,
            on_match=translate_action(action.nested, mcp_client)
        )]
    
    elif action.primitive == PrimitiveType.ADAPT:
        # ADAPT 把原 action 的 params 替换
        return [HACallService(
            domain=action.target.domain,
            service=action.target.service,
            entity_id=action.target.entity_id,
            data=action.target.data  # 已经是 adapted data
        )]
```

**Trace 一遍 S2.11 plan**:

```
Action 1: fan.bathroom_fan.turn_on()
  → HACallService(domain="fan", service="turn_on", 
                  entity_id="fan.bathroom_fan", data={})
  → MCP: ha.call_service("fan", "turn_on", "fan.bathroom_fan", {})
  → HA REST: POST /api/services/fan/turn_on {"entity_id": "fan.bathroom_fan"}

Action 2: DENY(light.bathroom_light.turn_off)  
  → HASuppress(...)
  → MCP: NO CALL (suppressed locally by VERDICT executor)
  → If automation rule subsequently calls turn_off, VERDICT intercepts

Action 3: AFTER(binary_sensor.bathroom_motion == 'off') 
            DELAY(5m) light.bathroom_light.turn_off()
  → HAStateListener(entity="binary_sensor.bathroom_motion", op="==", value="off",
                    on_match=HAScheduledCall(delay="5m", 
                                              inner=HACallService(...)))
  → MCP: ha.subscribe_state("binary_sensor.bathroom_motion", callback)
  → Wait for state == "off" event
  → On match: setTimeout(5min)
  → On timer: MCP: ha.call_service("light", "turn_off", "light.bathroom_light", {})
```

### 3.5 MCP server 实现细节

**MCP server 是一个 separate process**，stdin/stdout 跟 VERDICT 通信:

```python
# verdict_ha_mcp_server.py
from mcp import Server, Tool
import requests

class HAMCPServer(Server):
    def __init__(self, ha_url, ha_token):
        super().__init__("verdict-ha-bridge")
        self.ha_url = ha_url
        self.ha_token = ha_token
    
    @tool("ha.call_service")
    def call_service(self, domain: str, service: str, 
                     entity_id: str, data: dict) -> dict:
        response = requests.post(
            f"{self.ha_url}/api/services/{domain}/{service}",
            headers={"Authorization": f"Bearer {self.ha_token}"},
            json={"entity_id": entity_id, **data}
        )
        return response.json()
    
    @tool("ha.get_state")
    def get_state(self, entity_id: str) -> dict:
        response = requests.get(
            f"{self.ha_url}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {self.ha_token}"}
        )
        return response.json()
    
    @tool("ha.subscribe_state")
    def subscribe_state(self, entity_id: str, callback_id: str):
        # 用 HA WebSocket API 注册 state listener
        # 状态变化时 invoke callback_id
        ...
```

**为什么用 MCP 而不是直接 HTTP call**:

1. **标准化接口**: 未来支持 Matter / OpenHAB / SmartThings 只需换 MCP server，VERDICT 核心不变
2. **可审计**: MCP 调用全部 logged，便于 forensic
3. **可 mock**: Testing 时用 mock MCP server，不需要真 HA instance
4. **跟 LLM 工具调用同协议**: 如果 plan synthesizer 用 LLM，LLM 可以直接通过 MCP query device state——架构统一

### 3.6 一个 corner case: HA 没有直接的 "DENY" primitive

HA 的 service call 是单向的——你只能 "call service to turn on"，不能 "deny this rule from turning on"。

**VERDICT 的 DENY 是怎么实现的？**

两种方案:

**方案 A: Inline interception** (推荐)
VERDICT 作为 **proxy / middleware** 介于 HA automation engine 和 service executor 之间。所有 rule trigger 先经过 VERDICT，VERDICT 决定是否 forward 给 HA executor。

```
HA automation rule triggers
   ↓
VERDICT mediation cycle  ← intercept point
   ↓ (if not DENY)
HA service executor
```

**方案 B: Automation disable**
用 HA 的 `automation.turn_off` 暂时禁用某 rule，处理完后 `automation.turn_on` 恢复。

方案 A 更干净，但要求 VERDICT 在 HA 的 automation engine 内嵌 (HA add-on or custom integration)。

---

## Part 4: 这些内容写在 paper 的哪里

### 4.1 完整 paper 结构 + DSL/MCP 的位置

```
§1 Introduction
§2 Background and Related Work
§3 Conceptual Framework
   §3.1 Situation
   §3.2 Intent and Vocabulary
   §3.3 Specifications  
   §3.4 Attack Pattern Taxonomy

§4 VERDICT Architecture
   §4.1 Overview
   §4.2 Skills
   §4.3 World Dynamics Graph
   §4.4 Plan Synthesizer  
   §4.5 ⭐ Plan DSL              ← DSL syntax + semantics (1.5 页)
   §4.6 LTL Validator

§5 Implementation             ← 整章
   §5.1 System Components
   §5.2 ⭐ HomeAssistant Integration via MCP  ← MCP 翻译 (1 页)
   §5.3 Deployment Architecture (Tier A/B/C)

§6 Evaluation
   ...

§7 Discussion
§8 Conclusion
```

### 4.2 DSL 在 §4.5 写什么 (1.5 页)

具体 subsection 和大致字数:

| Subsection | 内容 | 字数 |
|---|---|---|
| §4.5.1 Design Rationale | 为什么 4+2 primitive；跟 binary mediator 对比 | 200 字 |
| §4.5.2 Syntax | BNF grammar (Figure)；example plans | 250 字 |
| §4.5.3 Type System | Dataclass definitions (Figure) | 200 字 |
| §4.5.4 Operational Semantics | 每个 primitive 的执行语义 (Table) | 300 字 |
| §4.5.5 Composition Patterns | 跨 AP 的 plan example 集合 | 250 字 |

**核心 figures/tables**:
- **Figure: DSL Grammar in BNF**
- **Table: Primitive × AP Coverage** (上面 Part 1.2 那张表)
- **Table: Operational Semantics** 
- **Figure: Sample plans for each AP**

### 4.3 MCP 在 §5.2 写什么 (1 页)

| Subsection | 内容 | 字数 |
|---|---|---|
| §5.2.1 Bridge Architecture | VERDICT ↔ MCP Server ↔ HA 三层架构 (Figure) | 200 字 |
| §5.2.2 Tool Specification | MCP 暴露的 tools 列表 (Table) | 150 字 |
| §5.2.3 Plan Translation Algorithm | DSL → MCP call sequence 的算法 (Algorithm box) | 300 字 |
| §5.2.4 DENY Implementation | Inline interception 设计；跟 HA core integration | 200 字 |
| §5.2.5 Platform Portability | Why MCP enables portability to Matter/OpenHAB | 150 字 |

**核心 figures**:
- **Figure: VERDICT-HA Bridge Architecture**
- **Algorithm: translate_plan_to_ha**
- **Table: MCP Tool Specification**

### 4.4 Appendix 内容

不放主文但保留在 appendix:

- **Appendix A: Complete DSL Grammar** (full BNF, 1 页)
- **Appendix B: Complete Plan Examples Across All APs** (7 个 AP × 平均 2 个 plan = 14 plans，2 页)
- **Appendix C: MCP Server Implementation Code** (or release as artifact)
- **Appendix D: HomeAssistant Integration Code** (or release as artifact)

### 4.5 总结: DSL + MCP 占 paper 多大篇幅

| Content | Paper 篇幅 |
|---|---|
| §4.5 DSL | **1.5 页** |
| §5.2 MCP integration | **1 页** |
| Appendix A-D | **3-4 页** (不计入主文 page limit) |
| **总计 main paper** | **2.5 页** (约占 ESORICS 14 页限制的 18%) |

---

## Part 5: 一些 honest 的设计 trade-off

写完上面后我必须告诉你几个**潜在 reviewer concern**:

### Concern 1: BNF grammar 你真要 parse 吗？

如果 plan 只由 plan synthesizer (LLM) 生成，你**实际上不需要 parser**——可以直接让 LLM 输出 JSON-structured plan，绕过 BNF。

**Trade-off**:
- 用 BNF + parser: paper 显得正式，但实现复杂
- 用 JSON schema: 简单，但 paper 写出来没那么"formal"

**推荐**: paper 里展示 BNF (formal claim)，实现用 JSON schema (因为 LLM 输出 JSON 最稳定)。BNF 是"等价规范"，paper 里 cite "implementation uses JSON-encoded equivalents for LLM output stability"。

### Concern 2: MCP 真的必要吗？

如果只对接 HA，**直接 HA REST API 就行**——不需要 MCP 这层抽象。MCP 的价值是 portability，但 paper 投 IoT venue 时，reviewer 不一定 care portability。

**Trade-off**:
- 用 MCP: 更通用、跟 LLM agent 生态接轨
- 直接 HA API: 简单、performance 更好

**推荐**: 实现两种都做。**论文展示 MCP** (跟 LLM 时代趋势接轨)，**评估用直连** (less infrastructure noise)。

### Concern 3: 你的 DSL 太简单会不会被批评？

只有 4+2 primitive 是**优势** (minimal sufficient)，不是劣势。但 reviewer 可能说"为什么不支持 LOOP / CONDITIONAL / 等"。

**预防性 framing**:

> "We deliberately restrict DSL to four temporal primitives, eschewing imperative constructs (loops, conditionals) that would complicate symbolic validation. The DSL is *intentionally Turing-incomplete*: any plan can be statically checked against LTL specs in polynomial time, a property essential for the validator's soundness."

把 "简单" frame 成 "designed for verifiability"——reviewer 没法批评。

---

## 一句话总结

> **DSL 含 4+2 primitive (EXECUTE/DENY/ADAPT/AFTER/DELAY + PARALLEL/SEQUENCE)，用 BNF 定义、Python dataclass 实现、operational semantics 描述执行。MCP 作为 VERDICT ↔ HomeAssistant 的标准 bridge，translate DSL primitive 到 HA service call。Paper 主文 §4.5 (1.5 页 DSL) + §5.2 (1 页 MCP) + Appendix (3-4 页)，总主文 2.5 页——占 ESORICS 14 页限制的 18%，是 paper 的具体技术 anchor。**

