
# Situation Definition

situation只是evidence dimentsion； 只是container 不是context？
自然语言描述activation predicate 来评估证据？而不是LLM理解situation， 这个问题怎么理解？
以及situation 和 activation_condition怎么对应的，activation condition到底要什么形式呢？



> 一个完整的 **Situation (情境上下文)** 是指在特定自动化规则被触发的瞬间（$t_0$），智能家居系统的全景状态切片。它为动态访问控制与情景化安全策略生成，提供完整的因果推理依据。

## 1. 元数据与高级活动上下文 (`meta` & `activity`)
此模块包含由上游时序模型（如应用层事件序列模型）推导出的高维上下文。
* **Activity Label**: 当前正在发生的核心人类活动。
* **Time Offset / Temporal Features**: 活动的持续时间或特定的时间特征（例如：已经持续了多久，或者发生在一天中的什么时间段）。



## 2. 设备状态架构 (`device_schema`)
* 一个静态的字符串列表，用来声明实体（Entity）在 `snapshots` 状态向量中的**绝对索引顺序**，确保时序数据的紧凑性与对齐。

## 3. 时序状态快照序列 (`snapshots`)
* 以触发瞬间（$t_0$）为基准，向前回溯的历史状态阵列。
* 每个快照包含一个相对时间戳 `t_min_before_trigger`（或以秒为单位的 `time_offset`）以及对应的状态向量。
* **状态差分（State Delta）**：相邻两个快照之间的物理量/状态变化构成了系统底层的物理事件流。

## 4. 规则触发瞬间与预期动作 (`trigger` & `proposed_action`)
* **Trigger Event**: 导致系统在 $t_0$ 瞬间打破静默、唤醒联动机制的精确边界条件（包含触发实体、触发类型、阈值及当前瞬时值）。
* **Proposed Action**: 规则被触发后，智能家居引擎**计划执行**的下步服务调用（Service Call），用于合规性检查（Compliance Check）。

---

# activation
> 通过将静态 Trigger 嵌入到 Situation 中，激活判定器（Activation Judgement Engine）能够进行两阶段安全规范（Sigma）评估：假设现在Situation就是系统相信的世界，那么当前应该执行哪一种property interpretation；

*需要回答，situation 和 activiation的关系？*

不是区分突变与渐变吧，我们从来不是一个异常检测的任务，只是说让你通过数据来了解现实世界到底发生了什么（最有可能理解）然后去做情景化的判定；对于一个动作该不该执行，要怎么执行；是要先了解为什么和原本的计划，对应的再去做调整？我不知道怎么说这个东西，只是很直觉


activity 能推断人类当下活动的长期意图？
acvtivity与tragency一起判定trigger产生的原因？

联合产生原因，当前物理环境、用户可能的意图；联合推理当前用户的需求是什么？然后trigger导致的action会破坏这些需求？这么理解吗？然后对应的弥合“这些需求”来调整策略。最终输出什么？是用来维持系统安全状态的约束，还是直接修改一些automation rule？ 

个人认为是安全约束？细化安全规则，因为有变动的只是特定的情境


从我们生成动态guideline

首先要区分 automation rule 和 spec；
automation rule；本身又具体的意图；
spec帮助看看是否完成其intent，或者破坏了其他的intent


