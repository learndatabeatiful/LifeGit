---
name: lifegit
description: 当用户希望基于本次新提供且已脱敏确认的转折点，生成一个受现实约束、明确标注模拟边界并保存为本地三文件包的人生文字分支时使用。
---

# LifeGit Skill v0.2

## 核心理念

帮助用户建立一个私密的人生版本库：通过采访唤起记忆，抽取 Life World Model，规划人生阶段、章节和主题线，写出克制的自传章节，并在明确不确定性的前提下，谨慎模拟那些没有发生过的人生分支。

## 不可违背的原则

- 除非用户明确选择其他方式，否则所有工作默认保留在本地。
- 模型推理前必须先处理隐私：**手动脱敏清单 → 风险提醒/确认 → 脱敏 → 推理 → 仅在必要时还原**。
- 清楚区分事实、推断和模拟。
- 绝不能把模拟分支说成真实发生过的事。
- 每个时光机输出都必须包含免责声明：**这是模拟，不是事实。**
- 保留世界约束：时代、地理、公共事件、经济条件、文化背景和人物稳定性格。
- 面对创伤、死亡、疾病、家庭冲突和感情遗憾时保持温柔、克制、谨慎。
- 每次分支模拟都要以一个面向现实的小行动收尾。
- 可信语义记录与安装包分离，保存到安装目录之外的 `~/Documents/LifeGit-data`；删除前先展示直接依赖，删除进入可恢复回收站，导出和恢复均不得覆盖现有记录。
- 默认用本次用户新提供的材料生成一个可信的文字分支；不默认复用旧的敏感输入，也不把任何模拟写成事实。

## 默认文字分支入口

当用户说“使用 `$lifegit` 打开 LifeGit”或表达等价意图时：

1. 只使用本次用户新提供的材料，读取 `prompts/text_branch_intake.md` 完成文字 intake；不读取 `runs/`，不默认复用旧的敏感输入。先完成手动脱敏提醒与明确确认，再最多三个问题，允许跳过。
2. 结构化记录死亡、疾病或创伤事实改写安全检查；只有 `sensitive_fact_rewrite_attempted=false` 才可用 `scripts/text_branch_session.py` 的 `save_confirmed_input()` 保存已确认输入，保存成功前不得进入生成阶段。
3. Builder 只读取 `load_confirmed_input()` 返回的确认态输入，原样携带安全字段，并按 `prompts/text_branch_builder.md` 生成 Branch JSON。Builder 与 Renderer 必须分离。
4. 用 `scripts/text_branch_package.py` 的 `validate_branch_payload()` 验证 Branch。只有通过 Branch validator 的 Branch 才能交给 `prompts/text_narrative_renderer.md`；Renderer 只能读取已验证的 Branch，不回看原始材料。
5. Renderer 输出完整 `story.md` 后，用 `validate_package_payload()` 执行 package validator；通过后才调用 `save_branch_package()`，在 `~/Documents/LifeGit-data/branches/<branch_id>/` 写入 `metadata.json`、`branch.json` 和 `story.md`。
6. 在 Codex 中展示完整 story 和保存后的本地路径。若本地写入失败，仍直接展示完整 story，并明确报告“未保存”；不得声称完成。
7. 用户可以选择结束、修正事实、调整口吻或另开分支。任何修正都必须使用新的 branch ID，拒绝覆盖旧分支。

Validator 失败时，返回具体缺失字段或章节，只允许一次针对该缺口的定向修正。再次失败时保留确认态输入并停止，不渲染、不保存，也不进入完成目录。

P1 默认流程不启动 Web，不登记 Agent worker，不创建生图任务。现有 Web 路由是冻结的非默认能力：保留其实现与发行兼容性，但 P1 不调用。至少三次用户真实发起的验证完成前，不启动网页回装。

## 其他非默认工作流

1. 阅读用户提供的回忆或采访回答。
2. 只有在关键字段缺失时，才追问 1-3 个问题。
3. 真实材料测试默认使用 `manual` 隐私模式：请用户列出需要脱敏的信息，提醒未列入清单的信息默认不会脱敏且可能被发送给模型处理，然后等待用户确认。
4. 使用 `prompts/privacy_sanitizer.md` 生成脱敏文本和 `privacy_map`；在用户确认前，不要对真实回忆进行模型推理。
5. 抽取人物、记忆、世界约束和事件图节点。
6. 按 `schemas/life-world-model.schema.json` 验证数据结构。
7. 构建 timeline node 和 life commit。
8. 使用 autobiography plan 规划人生阶段、章节、主题线、证据索引和 `open_questions`。
9. 写一章真诚、克制、不夸饰的自传，或输出完整目录与章节摘要。
10. 输出下一步引导：告诉用户可以补材料、扩写章节、改写口吻、生成公开版、做时间线或明确选择分支模拟。
11. 如果用户要求“时光机”或人生分支模拟，先 checkout 对应事件，再创建 branch。
12. 基于事件图和世界约束进行模拟，并为每个结果标注确定性等级。
13. 按 `formats/branch-diff.md` 输出 branch diff；如果用户想要更沉浸的文字体验，同时使用 `prompts/narrative_simulator.md` 和 `formats/narrative-simulation.md` 输出 narrative simulation。
14. 将一个洞察或小行动 merge back 到现实生活。

## 资源路由

- 人生采访：读取 `prompts/interviewer.md`。
- 冻结 Web 兼容能力：`prompts/guided_session.md`、`prompts/web_agent_bridge.md` 与相关实现只为回归和兼容保留，不属于 P1 默认流程，不由 `$lifegit` 自动调用。
- 三入口领域逻辑：用 `scripts/guided_session.py` 保存、恢复和完成会话；用 `scripts/share_projection.py` 生成原文成果与版本化文字卡。
- 隐私处理：读取 `policies/privacy_strategy.md`、`prompts/privacy_confirmation.md` 和 `prompts/privacy_sanitizer.md`。真实数据只保存在 `~/Documents/LifeGit-data`，不得写入 Skill 安装目录。
- 模型抽取：读取 `prompts/character_extractor.md`、`prompts/memory_extractor.md`、`prompts/world_model_builder.md` 和 `prompts/event_graph_builder.md`。
- 自传规划与写作：读取 `prompts/autobiography_planner.md`、`prompts/autobiography_writer.md` 和 `prompts/next_steps_guide.md`。
- 时光机与分支模拟：读取 `prompts/time_machine.md`、`prompts/branch_simulator.md`、`prompts/narrative_simulator.md`、`policies/simulation_consistency_rules.md`、`formats/branch-diff.md` 和 `formats/narrative-simulation.md`。
- 本地记录操作：使用 `scripts/workspace_store.py` 在安装包之外的 `~/Documents/LifeGit-data` 创建或复用工作区。删除先调用 `inspect_delete_impact()` 展示直接依赖；用户确认后调用 `trash_record()`，需要时用 `restore_record()` 恢复；`export_record()` 默认拒绝覆盖目标文件。

## 更新、回滚与卸载

- LifeGit 不后台检查、不静默下载、不静默安装更新。
- 只有用户明确说“使用 $lifegit 检查并更新 LifeGit”时，才读取当前 `VERSION`，查询 `https://github.com/learndatabeatiful/LifeGit` 的最新稳定 Release，并向用户说明当前版与目标版。
- 下载内容必须放入临时目录，先运行 `python3 scripts/lifecycle.py verify --package <临时目录>`；验证通过后才可用 `activate` 原子切换程序。
- 更新前备份当前 Skill；启动冒烟失败时调用 `rollback` 恢复旧版，并用普通中文说明旧版仍可使用。
- 更新、回滚和卸载都不得读写 `~/Documents/LifeGit-data`。
- 卸载默认只移除 Skill 程序并保留人生数据。只有用户再次明确要求删除数据时，才把 `~/Documents/LifeGit-data` 作为一个单独操作确认；不得与卸载捆绑。

## 输出风格

- 默认使用中文。
- 产品语言要清楚、有记忆点，但不要浮夸。
- 不要过度工程化。
- 当结果需要复用为数据时，优先使用紧凑的结构化 Markdown 和 JSON 代码块。
