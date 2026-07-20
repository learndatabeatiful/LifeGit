# 工作流 02：从人生采访到 Life World Model

1. 运行 `prompts/interviewer.md`，补齐必要细节。
2. 执行隐私脱敏。
3. 抽取 Character、World、Memory 和 Event Graph 四层。
4. 按 schemas 验证每一层结构。
5. 缺失事实记录到 `open_questions`，不要编造。

## 最小输出

```json
{
  "version": "0.1",
  "privacy_level": "medium",
  "character_layer": [],
  "world_layer": [],
  "memory_layer": [],
  "event_graph": [],
  "timeline": [],
  "open_questions": []
}
```
