# 题目Situated Runtime Mediation
老师说不够security

Dynamic Situation 缺失导致的策略失效；防止上下文
思考，根据用户输入直接生成策略的内容是？


**Problem.** 智能家居自动化规则(TAP/IFTTT 风格的 IF-THEN property)是静态的:它在作者默认的隐含场景里正确,但现实情境会让同一条规则的动作在某些 cause/trajectory/occupant-state 下反而违背它本来的目的(夜里走廊亮灯——但隔壁有人在睡;高温开空调——但家里没人)。
Gap. 现有工作要么做静态规则冲突检测/改写,要么做 TAP 规则合成,但都停留在 trigger 那一刻可读的状态上,无法处理"原因、趋势、占用者状态、覆盖性紧急情况"这些 trigger 瞬间不可见的维度。
----
*comments：你的cause/trajectory/occupant-state第一要在问题定义的时候重新定义，而在后续的解决方案时要搞清楚和situation定义的关系*
----

**Insight.** 一条 property 的动作绑定在某个设备上,但它的 intent 没有。把 intent 从设备上"抬起来"(intent lift),就能用三个 domain-general 的算子(SCOPE / EXCEPT / GENERALIZE)把一条规则展开成一组情境化的 spec 片段(sigma),其中 cause-driven 的反转才会浮现。
Solution. 一条离线流水线(Spec Variants Generation → Convergence → Spec Corpus)喂给运行时中介(Spec Activation → Action Mediation),让 LLM 在被 sigma 约束的前提下做情境化决策,而不是静态改写。
Impact. 相比静态 baseline,在 X% 的情境里能正确抑制/反转/降级原动作,且产出可复用的 invariant policy。 (数字待你补充——这是整个 impact 句的支点,现在是空的。)


# pipeline 
首先，基于现有*智能家居*科研工作定义的correctionness properties，或者security policy（请注意，不是automation rule）；以及基于一些template用户输入的个人偏好作为输入；我们基于LLM去做一个exploration，来帮助生成各种情景化的安全与偏好spec；这一套spec最终经过用户确认，以及收敛，作为后续知道动态情景化做指导；

进一步，在online的阶段；我们组建一个叫做situation的数据类型，后续我提供给你例子，来让你了解；然后基于situation，让LLM了解当前发生了什么事情，一条自动化规则，是怎么发生的？进一步，对于这个规则可能会执行的后果序列，我们提取出来（e.g.，Rule1的trigger event导致了一系列规则的触发，是一个explicit chaining；或者，一个打开窗户的action，导致室温下降）；最后，这两者一起询问LLM，当前的situation，激活了那些spec？ 激活后，怎么guide这个原本的action？

因为有些规则运行不在runtime的时候你是无法落在具体的设备状态上的，也无法考虑任何边缘情景，我们之前探索，落地的各种情景化碎片可以guide这种场景，最终的invairawnt policy generation，是从这次具体的运行过程中，生成了具体的，可复用的后续策略。无需经过LLM的判断


# 主要问题
我们今天先解决spec variants generation这个部分？这个部分好多东西我都搞不明白，现在有一个skill的draft

# 核心模块
## Spec Variants Generation
1. 各个操作符是*不平行*的，例如，原版输入的property还是device state的表示；那么，。你的scope；expect貌似还是保留了原版的device state action？
感觉scope时给trigger+了更细粒度的情景文本描述；给except也是加了情景化的描述+一个取反例的的action；但是到generalize；就整体“拔高”了；那么为什么不直接用拔高的trigger；与action，来对scoope except？ 
请你结合我们的具体需求；首先梳理、总结问题；进一步清晰的定义输入输出；说为什么能够符合这样的需求
2. 各个操作符的*输出*是不确定的，帮我确定
3. 最终spec的表现形式**一定**要包含哪些字段呢？
4. 

我可以提供任何你需要的东西，比如skill的draft；或者 一些现有的案例；这个skill有很多结构化的问题。

:有多少条规则,存在一个"触发瞬间状态合法、但在某 cause/occupant/override 情境下动作背叛 intent"的情境?
这个如何统计？这个根本没有办法量化。所以我们的框架的第一个部分是基于现有工作的policy/property（记住，不是automation rule）去做一个有限的，经过确认的，可以用作后续ground truth的 情景化spec corpus，你理解我的意思吗

但是有个问题，首先cause这些的分类，都是由activate的prompt来决定的对吗？
那么如果 本身有一条原始的property：用户不在家的时候锁门——>在家里火灾发生了，继续锁门；者确实没有违背本身的意图，但是破坏了我们commen sensce的安全；你可以理解我的意思吗？所以把s方法分解的到底是谁；分解的方法对不对；对于 betray s的定义到底是不是我们想要表达的呢？



# Q & A

1. **本质区别是什么？**  
   你的三个算子相对于已有工作（Menshen, Salus, AutoTap, HomeGuard, IoTGuard, 以及各种“LLM for home automation”工作）的根本区别在哪？  
   - AutoTap 已经能从自然语言/属性合成 TAP 规则并做时序属性检查。你的 EXCEPT（找动作背叛 intent 的情形）和它们的冲突检测，在机制上有何本质不同？  
   - 如果答案是“我们用 LLM 所以能处理 cause-evidence”，那贡献就退化成“把已有 pipeline 的某一步换成 LLM”，这属于 weak reject 量级的新颖性。

2. **必须证明存在一类静态方法原理上无法捕获的背叛**  
   你要证明存在一类反转（如“喂养次生危害”“加剧系统性危机”这种 cause-driven betrayal），是任何静态方法在原理上无法捕获，而你的方法能捕获的。  
   - 笔记里 skill 文档自己承认“离线不可判定，只能下游测量”，那么论文的核心卖点在原理上不可证，只能靠实验。如果实验不够硬，novelty 直接崩。

3. **现象普遍性（生死线）**  
   R.3 那类“intent betrayal”情境，在真实的 property 集合里普遍吗？  
   - 如果你能证明“83 条里有 N 条存在这种静态方法看不见的情境”，且 N 不小——这是核心证据。如果 N 很小（比如只有两三条），现象太边缘，撑不起一篇顶会。先做这个统计。

4. **量化对比**  
   你的方法在这些情境上，比 IoTGuard/TAPFixer 强多少？不能只说“它们看不见”，要量化“在 M 个情境里，它们误判 / 你正确”。没有这张对比表，会被直接 reject。

5. **Intent lift 是 essential 还是 cosmetic？**  
   之前已经论证了“为什么需要它”，但 reviewer 还会要经验证据。

   
---

## 2. Property/Preference 与 Intent 的来源及必要性

1. 为什么不直接用用户输入的 intent 来生成规则？property / preference 到底从哪来？  
   - 一个 property 的意图可能不一致；用户定义不全；安全相关必须有规范背书。  
   - preference 也可以由用户输入，但如果没有一个完整的、可验证的过程，只说一句“我喜欢暖光”，根本不知道用在哪里。个人认为 preference 仍需考虑。

2. 从 property 提取 intent 的必要性？  
   - 这个问题和上一条类似。能否做一个 ablation：直接跑三个算子，跳过 intent 提取？但质量怎么衡量？而且现在对 intent 的量化根本没有道理。  
   - 三个算子的判定边界和 coverage 也需要明确。

---
## 3. 三个算子的设计必要性、平行性与输入层级

1. **三个算子的存在必须有结构性空洞要填**  
   - X（三个算子）之所以存在，是因为问题结构里必须有一个 X 来填的洞；没有 X，这个洞在原理上没人填。这是分析性的、事前的，不应该依赖跑分。  
   - “这三个各自堵一个独立的洞，少一个就有一类规则没人管” —— 把一条规则变成“在各种情况下到底该怎么做”，在逻辑上必经三道关，每道关回答一个独立问题，互不能替代。三个算子不是“我挑了三个”，而是“这条流水线本来就有三个环节”。如果无法证明这一点，就要修改算法定义。
   - 

2. **Scope 和 Except 会重叠吗？动作互斥吗？**  
   - 感觉 scope 是告诉你某些情况才该干嘛，except 是指某些情况不能干嘛；但动作是否互斥？不太清楚。  
   - 而且感觉 generalize 出来的 intent（trigger 的延伸） / goal（action 的延伸）才应该是 scope 和 except 的输入。

3. **输入层级断代问题**  
   - 原始输入中，SCOPE/EXCEPT 还在和设备名字、开关状态打交道（设备层），但 GENERALIZE 突然跳到了抽象的意图和物理环境（意图层）。数据在流水线里层级断代。  
   - 为什么不直接在流水线第一步就做 Intent Lifting，把原始规则 P = ⟨Trigger_dev, Action_dev⟩ 统一翻译为不包含任何设备名字、只包含物理状态改变趋势的抽象意图 P*？  
   - 如果把 P* 作为三个算子的唯一通用输入，请证明：这样做在运行 SCOPE 和 EXCEPT 时，会不会因为丢掉了具体设备的硬件物理特性（例如窗户有开合度、空调有能耗差异），导致生成的边界和异常条件太模糊，无法指导后续的精确中介？

4. **平行性：输入数据类型不一致**  
   - 如果 SCOPE 和 EXCEPT 的输入依然是具体的设备状态（如“开空调”），而 GENERALIZE 用抽象的意图（如“降温”），三者输入数据类型就不一致。  
   - 请设计一个统一的转换函数（如 Intent Lifting），输入 (Device, State)，输出统一的物理变量变化趋势。并证明：如果直接把统一抽象物理趋势作为三个算子的共同输入，会不会导致 Scope 和 Except 的约束粒度过粗，从而漏掉设备特有的安全隐患？







---

## 4. Spec 生成：输入来源与输出字段的精简

### 4.1 输入
- 期望输入是：已有的、为安全正确性背书的外部 property 集合，加上用户按照一定模式、标准输入的 preference。  
- 需要说清楚：用了哪些 paper 的 property 集合，你与它们的关系是什么（citation + positioning）。

### 4.2 输出应精简为最小集合
- 认为 `move review_state` 之类字段没有意义，因为无论什么情况都需要让用户审计。  
- `primary_protect` 缺失有意义，但所有和安全相关的必须无条件保护和告知用户；只有舒适度、可用性这类可以做 trade off。每个标签都需要引用具体的 reference 来确定它们的 position。

### 4.3 激活条件相关
- `activation`：触发断言，实质是输入一个 situation 结构，让 LLM 理解是否属于 activation 的自然语言描述。activation 有什么限制吗？  
- `observable/signal_class`：感觉根本没用。

### 4.4 激活后怎么解决：abstract_action
- `abstract_action`：行为改写原语，一个动作重写算子。包含不做动作/反指令/抽象动作——在策略层翻译，真的有必要吗？打通了吗？和 intent 是什么关系？生成指导方针是什么？为什么一定要生成成这样？  
- 既然我们是给后续 runtime 的 guideline，为什么一开始不确定下来？为什么没有确定性的定义？是什么问题导致必须在这里不给确定性？这个不确定性又如何定义？给一个具体例子。


### 4.5 冲突消解
- `primary_protect` 和 `trades_off_against`：最大问题是所有安全相关的绝不妥协，只有可用性那些内容可以 trade off。  
- 但如果可用性被 trade off 了，偏好的意义是什么？

### 4.6 泛化落地到具体设备
- `generalized_class`：具体影响的物理通道和实现设备。这个和 (2) abstract_action 的意义都需要讨论。

### 4.7 在线消费所需的最小刚性字段
- 离线生成的 Spec 片段最终是给在线拦截和重新细化；调度规则的的模块（可能是LLM可能是代码）消费的。为实现“无模型的确定性冲突消解”（两条规则打架时，代码能查表比大小，不依赖 LLM 现场猜），输出中必须包含哪些提供偏序或利益对冲的刚性字段？  
- 例如 `generalized_class` 中的封闭标签（`air_channel`, `emergency_event` 等），如果彻底删掉它，在线决策引擎在需要跨规则索引物理通道时，会不会出问题？




### 三个算子
- **解决的问题**： 如果要保留一个算子的必要性，必须提炼、构想
X的存在（三个算子的存在）——是因为问题结构里必须有一个X必须填的洞；没有X，这个洞在原理上没有人填；分析性、事前，不应该依赖跑分。如果无法满足这个需求，这三个问题如果不是平行的，那么就是要修改算法的定义。即

因为我们无法我证明完备性！
以及scope、except总感觉会重叠？其实也不重叠；scope是告诉你某些情况才该干嘛；eccept是指某些情况不能干嘛； 动作是互斥的？我不太懂啊；而且体感generlized出来的inetnt（trigger的延伸）/ goal（actionn的延伸）才该是scope和except的输入。

好吧如果我又发散又不grounded了，请你告诉我。 

- **输入**原始输入、SCOPE/EXCEPT 还在和设备名字、开关状态打交道（设备层），但 GENERALIZE 突然跳到了抽象的意图和物理环境（意图层）。数据在流水线里层级断代了。
为了让三个算子完全齐平，为什么我们不直接在流水线的第一步就进行 Intent Lifting（意图提升），把原始规则 $P = \langle \text{Trigger}_{\text{dev}}, \text{Action}_{\text{dev}}\rangle$ 统一翻译为不包含任何设备名字、只包含物理状态改变趋势的抽象意图
如果我们把 $P^*$ 作为三个算子的唯一通用输入，请向我证明：这种做法在后续运行 SCOPE 和 EXCEPT 时，会不会因为丢掉了具体设备的硬件物理特性（例如：窗户有开合度、空调有能耗差异），导致生成的边界和异常条件太模糊，无法指导后续的精确中介？

- **定义的平行性**
- ****
如果输入给 SCOPE 和 EXCEPT 的依然是具体的设备状态（如‘开空调’），而 GENERALIZE 却用抽象的意图（如‘降温’），那它们三者的输入数据类型（Data Type）就不一致。

请帮我设计一个统一的转换函数（如 Intent Lifting），输入 (Device, State)，输出统一的物理变量变化趋势。并向我证明：如果直接把这个统一的抽象物理趋势作为三个算子的共同输入，会不会导致 Scope 和 Except 的约束粒度过粗，从而漏掉设备特有的安全隐患？”

“离线生成的 Spec 片段（Sigma）最终是给在线拦截和重写动作的代码消费的。为了把结构体（Schema）砍到最简、毫无冗余，请帮我逆向分析：

在线中介引擎如果要实现‘无模型（Model-free）的确定性冲突消解’（即当两条规则打架时，代码能查表比大小，不依赖 LLM 现场瞎猜），输出中必须包含哪些提供偏序或利益对冲的刚性字段？

比如 generalized_class 中的封闭标签（air_channel, emergency_event），如果我彻底删掉它，在线决策引擎在需要跨规则索引物理通道时，会不会



contribution，我们必须要把这个input转化为一种合理的 reaonsbale的处理形式；以及对于三种算子有一种设计上的什么样的设计？

输出：


## wdg world dynamic graph
TODO: Prompt

是对世界动态的一个建模，用来模拟一个动作执行后会引发什么，如何定义这一块的技术难点，和建模这一块的技术难点。？因为我原本根本就没有具体的技术含量。呜呜呜。
⬇️ 如果开源，以及现有wdg的设置与代码，可以复用？ 给个指令/
TAPFixer 的物理+时延建模肩膀上(TAPFixer 已经把显式/隐式时延、物理交互对环境属性的影响建进自动机)。你引它、复用它、说"我们用它做情境/轨迹生成器",这是合法且省事的



## 问题

corpus 的coverage 和benchmark 的覆盖面？
corpus这么大？ 我们benchmark 创建的situation才这么少，怎么做？

corpus 大 / benchmark 小:这俩量本来就不该相等。Corpus = 离线生成的 σ 片段(覆盖 property 空间);benchmark = 运行时测试的情境(覆盖 betrayal 现象)。你要的不是数量匹配,是分层覆盖:benchmark 情境按 betrayal taxonomy(三算子 × cause/occupant/override)分层抽样,并给一个覆盖性论证说"每一类我都打到了"。小而分层 >> 大而随机,对一个"现象类"论文尤其如此。

**但是你的cause/occupant/override**的分层不合理



## baseline
AutoTap
Tapfixer
ContexIOT


