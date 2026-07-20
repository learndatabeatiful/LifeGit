# LifeGit Web Agent 桥接

1. 使用固定工作区 `~/Documents/LifeGit-data` 运行本地 Web；在会回收后台进程的环境中保持该工具会话运行。
2. 只登记当前会话实际可调用的能力。只有当前会话实际暴露了图片生成工具时，`image_generation.available` 才能为 `true`。即使宿主是 Codex，也不能仅凭宿主名称声称 GPT Image 可用；模型 ID 不可见时填 `null`。
3. 用最长 30 秒的 `next-job` 有界等待，不进行无休止轮询。
4. `text_enhancement` 只处理任务中的脱敏字段，返回 `fragment_markdown` 和一至三个带 `exact_quote` 或 `light_edit` 的核心句，不增加事实。
5. `image_background` 只生成无文字的抽象背景，不生成冒充现场的照片；将工具产物本地路径写入结果 JSON。
6. 工具不可用、配额不足或被拒绝时调用 `fail-job`；不要自动重复消耗生成次数。
