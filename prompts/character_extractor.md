# Prompt：人物抽取器

从脱敏回忆中抽取人物卡。不要把人物写成剧情工具；要保留稳定性和限制。

## 抽取字段

- id
- display_name / token
- relation_to_user
- traits
- values
- fears
- motivations
- communication_style
- relationship_history
- key_memories
- behavior_constraints
- confidence

## 规则

- 明确区分“文本明确说了”和“合理推断”。
- 没有证据就填 `UNKNOWN` 或留空数组。
- 对父母、恋人、朋友、老师、同事等，重点记录关系变化和行为约束。

## 输出

输出匹配 `schemas/character.schema.json` 的 JSON array。
