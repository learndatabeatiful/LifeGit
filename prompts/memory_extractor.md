# Prompt：记忆抽取器

把一段人生回忆整理为 Memory Layer。重点不是摘要，而是保留能被自传写作和时光机使用的细节。

## 抽取字段

- date / period
- place
- people
- event_summary
- raw_materials
- emotions
- sensory_details
- importance_score
- unresolved_feelings
- related_music / photos / text
- source
- confidence

## 规则

- 时间不确定时用自然语言，如 `高中某个夏天`。
- 情绪允许复杂并存，如 `开心` 与 `失落`。
- 不补造不存在的照片、音乐或文字。

## 输出

输出匹配 `schemas/memory.schema.json` 的 JSON array。
