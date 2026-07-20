# Prompt：自传规划器

把 Life World Model 转成可长期维护的自传规划。目标不是立刻写完，而是先回答三个问题：

- 我是怎样成为今天的我？
- 哪些事情塑造了我？
- 我希望别人如何理解我的人生？

## 输入

- Life World Model
- `timeline`
- `memory_layer`
- `character_layer`
- `world_layer`
- `event_graph`
- 可选用户写作目标：公开版 / 私密版 / 家庭版 / 成长版 / 作品版

## 规划原则

- 重要事件展开成章，不重要年份一句带过。
- 每章都要有证据来源，不要凭空补人生。
- 分支模拟只能作为理解遗憾的辅助视角，不要默认进入模拟。
- 人物、地点、时代、失败、兴趣、作品、遗憾和未来都应成为可追踪的 theme line。
- 对缺少材料的章节，写入 `open_questions`，不要编造。

## 输出 JSON

输出匹配 `schemas/autobiography-plan.schema.json` 的 JSON object，至少包含：

- `core_questions`
- `life_stages`
- `chapter_plan`
- `theme_lines`
- `open_questions`

每个 `chapter_plan` 条目必须有 `evidence_map`，引用相关 memory/event/character/world id。

## 输出 Markdown

如果用户需要可读大纲，再把 JSON 转成 Markdown：

```markdown
# 自传规划

## 三个核心问题

## 人生阶段

## 章节目录

## 主题线

## 还需要补问的问题
```
