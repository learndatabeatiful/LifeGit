# 工作流 01：LifeGit v0.1 端到端流程

## 目标

从一段原始回忆开始，完整走到 branch diff 输出。

## 步骤

1. **输入回忆**
   - 用户提供一段人生回忆。
   - 如果缺少时间、地点、人物或情绪，最多追问 3 个问题。

2. **隐私优先**
   - 真实 v0.1 测试默认使用 `manual` 隐私模式。
   - 请用户手动列出需要脱敏的姓名、地点、学校、公司等信息。
   - 明确提醒：未列入清单的信息默认不会脱敏，后续可能会被发送给模型处理。
   - 使用 `prompts/privacy_sanitizer.md`。
   - 产出脱敏文本和 privacy map。
   - 在模型推理前，请用户确认脱敏文本。

3. **抽取模型层**
   - 人物：`prompts/character_extractor.md`。
   - 记忆：`prompts/memory_extractor.md`。
   - 世界约束：`prompts/world_model_builder.md`。
   - 事件图：`prompts/event_graph_builder.md`。

4. **创建可信语义记录**
   - 为可核验内容写入事实层；为用户主观叙述写入回忆层；为当前解释写入理解层。
   - 只有用户明确选择时才创建模拟层；模拟不得写回事实或回忆。
   - 使用 `scripts/workspace_store.py` 的工作区操作保存、导出、回收或恢复记录。

5. **构建时间线**
   - 使用 `prompts/timeline_builder.md`。
   - 标记节点是否可以 checkout。

6. **规划并写自传**
   - 使用 `prompts/autobiography_planner.md` 生成 autobiography plan。
   - 使用 `prompts/autobiography_writer.md` 写章节或全书摘要。
   - 语气保持真诚、克制、不表演；不要默认展开分支模拟。

7. **创建 life commit**
   - Commit id 格式：`life_<YYYYMMDD_or_period>_<slug>`。
   - 包含 timeline node、event id、memory id 和摘要。

8. **Checkout 并创建 branch**
   - 使用 `prompts/time_machine.md` 执行 checkout。
   - 用户指定一个替代选择。
   - 使用 `prompts/branch_simulator.md`。

9. **Diff 并 merge back**
   - 输出 `formats/branch-diff.md`。
   - 用一个面向当前生活的小行动收尾。

## 验收标准

- privacy map 存在。
- Life World Model 的四个核心层存在。
- 时间线至少有一个节点。
- 自传不包含无来源事实。
- Branch 输出包含“这是模拟，不是事实。”
- Diff 区分高、中、低三档确定性。
- 最终输出包含一个现实可执行的 merge-back 行动。
