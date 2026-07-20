# Prompt：时间线构建器

基于 Memory Layer 和 Event Graph 生成人生时间轴节点。

## 输出字段

- time / date
- place
- event
- related people
- emotions
- importance_score
- follow_up_impact
- can_checkout
- linked_event_id
- tags

## 规则

- 时间轴是给用户复盘的，不是给外人猎奇的。
- `can_checkout` 需要同时考虑：是否有选择点、是否足够安全、是否有足够上下文。
- 节点标题要简洁，有画面感。

## 输出

输出匹配 `schemas/timeline.schema.json` 的 JSON array。
