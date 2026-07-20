# Prompt：事件图构建器

把记忆转成事件图谱，不只排时间顺序，还要表达因果、后果和替代选择。

## 抽取字段

- event
- causes
- consequences
- related_people
- related_memories
- decision_point
- alternative_choices
- emotional_result
- long_term_impact
- simulation_allowed
- sensitivity
- confidence

## 规则

- 只有存在可改变选择时，`decision_point=true`。
- 亲人去世、疾病、创伤等高敏感事件默认 `simulation_allowed=false`，除非用户明确要求温柔反思。
- 替代选择必须受人物和世界约束限制。

## 输出

输出匹配 `schemas/event.schema.json` 的 JSON array。
