# 工作流 03：自传规划与章节写作

1. 读取 Life World Model、timeline、memory_layer、character_layer、world_layer 和 event_graph。
2. 使用 `prompts/autobiography_planner.md` 生成 autobiography plan。
3. 明确三大核心问题：我如何成为今天的我、什么塑造了我、希望别人如何理解我。
4. 按人生阶段规划章节；不重要年份一句带过，关键事件展开成章。
5. 为每章建立 `evidence_map`，引用 memory/event/character/world id。
6. 输出 `open_questions`，提醒用户补充缺失材料。
7. 使用 `prompts/autobiography_writer.md` 写单章或全书摘要。
8. 添加事实核对区块，列出来源事实、推断和 UNKNOWN。
9. 使用 `prompts/next_steps_guide.md` 输出下一步引导，告诉用户可以补材料、扩写章节、改写口吻、生成公开版、做时间线或明确选择分支模拟。

## 输出形态

```markdown
## 自传规划

- 三个核心问题：
- 人生阶段：
- 章节目录：
- 主题线：
- open_questions：

## 自传章节

...

## 事实核对

- 来源事实：
- 推断：
- UNKNOWN:

## 下一步你可以做什么

- 推荐：
- 可选：
```
