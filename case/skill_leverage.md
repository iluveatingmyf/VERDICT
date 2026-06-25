上面是一个 skill。请严格按它的流程处理下面这一条 property:
不要省略任何一个 move,按 Step 0 → SCOPE → EXCEPT → GENERALIZE 的顺序走,
最后输出 skill 里规定的那个 JSON schema(完整的 sigmas 数组 + user_checklist)。

要求:
- abstract_action 必须是抽象目标动词或 no_action,不能出现任何 entity_id 或 service call。
- 每个 sigma 标全字段:move / protect_target / temporal_scope / intent_served /
  abstract_action / observable / signal_class / static_rewriteable / derived。
  (注意:没有 direction 字段——方向由 abstract_action 与原动作对比读出)
- 对每条 GENERALIZE sigma,其 activation 必须【显式枚举泛化类的成员】,
  尤其是原 trigger 没提到的非显而易见成员,不能只写一个抽象类名。
- 跑完后,在 JSON 之外用三五句话告诉我:intent_lifted 是什么,
  以及 GENERALIZE 长出的 family-level sigma 落到了哪个新场景/新对象、
  它的 activation 把哪些非显而易见的成员枚举了进去。


property:
IF the user is not at home / not nearby-home, the door should be locked.



IF the user is not at home / not nearby-home, the security
camera should be turned on.


IF 

IF CO is detected, the window should be opened.
或者


