# LifeGit

从本次新提供、已脱敏确认的一个人生转折点，生成一份受现实约束的“另一种今天”。

> 当前正式支持：macOS + Codex 桌面版｜版本：v0.2.0｜作者：learndatabeatiful

## 现在就安装

开始前，请确认你已经打开 Codex，并且当前网络能够访问 GitHub。

**你要做什么**

把下面整段复制给 Codex：

```text
请使用 $skill-installer 从这个 GitHub 仓库安装 LifeGit：
https://github.com/learndatabeatiful/LifeGit

安装完成后，使用 $lifegit 打开 LifeGit。
私人数据目录固定为 ~/Documents/LifeGit-data。
如果 Skill 暂未被识别，请告诉我是否需要重启 Codex。
```

**你应该看到什么**

Codex 告诉你 LifeGit 已安装，并请你提供本次想回看的单一转折点和唯一替代选择。

**如果没有看到，怎么办**

让 Codex 检查安装结果；如果 Skill 暂未识别，重启一次 Codex，再发送“使用 `$lifegit` 打开 LifeGit。”。不要反复覆盖安装。

## 默认文字分支入口

每次开始都使用你本次新提供的材料，不自动寻找或复用旧材料。

**你要做什么**

1. 提供一个已经手动脱敏的单一转折点，并且只改变一个唯一替代选择。
2. 阅读隐私提醒并明确确认继续；未列入脱敏清单的信息默认不会自动脱敏，并可能被发送给模型处理。
3. 完成死亡、疾病或创伤事实改写安全检查；如果尝试改变这类事实，流程停止且不保存。
4. 回答最多三个问题；可以跳过，LifeGit 不会追加补问。

LifeGit 随后分离执行 Builder、Branch validator 和 Narrative Renderer。只有通过 Branch validator 的 Branch 才进入 Narrative Renderer。通过 package validator 后，才会保存结果。

**你应该看到什么**

Codex 展示完整 story 和本地路径。每个完成的文字分支保存在：

```text
~/Documents/LifeGit-data/branches/<branch_id>/
  metadata.json
  branch.json
  story.md
```

你可以选择结束、修正事实、调整口吻或另开分支。任何修正都使用新的 branch ID，不覆盖旧结果。

**如果没有看到，怎么办**

如果 validator 失败，Codex 会指出具体缺失字段或章节，并只允许一次针对缺口的修正。再次失败时保留已确认输入并停止。如果本地写入失败，Codex 仍展示完整 story，并明确报告“未保存”，不会声称完成。

## 隐私与保存边界

真实材料和结果只放在 `~/Documents/LifeGit-data`，不写入 Skill 安装目录。每次都从本次新提供且已脱敏确认的输入开始，不默认复用旧的敏感输入。

**本地存储不等于模型完全不接触内容。** 只有你确认提交的脱敏内容进入模型；未列入脱敏清单的信息默认不会自动脱敏。若不确认或死亡、疾病或创伤事实改写安全检查不是明确安全值，流程停止，不保存确认态，也不进入 Builder。

## 冻结的非默认 Web 兼容能力

现有 Web、Agent worker、分享卡和图片相关资产只为发行兼容性保留，不由 `$lifegit` 默认入口启动。默认文字分支流程不启动 Web、不登记 Agent worker、不创建图片任务。至少三次用户真实发起的文字分支验证完成前，不进行网页回装。

## 手动更新、回滚和卸载

LifeGit 不后台检查或静默安装更新。需要更新时发送：

```text
使用 $lifegit 检查并更新 LifeGit。
```

Codex 会先说明当前版和目标版，验证下载包并备份旧程序，再切换版本；验证或启动失败会恢复旧版。更新和回滚都不修改 `~/Documents/LifeGit-data`。

卸载时告诉 Codex“使用 `$lifegit` 卸载 LifeGit，但保留我的人生数据”。**卸载 LifeGit 不会删除人生数据。** 删除 `~/Documents/LifeGit-data` 是另一件事，必须由你再次明确确认。

## 按你看到的现象排查

- 找不到 `$lifegit`：重启一次 Codex，再检查安装结果；不要重复覆盖安装。
- 没有进入文字 intake：让 Codex 重新读取 LifeGit Skill 的“默认文字分支入口”。
- validator 失败：按具体缺口修正一次；再次失败就停止，不把未验证结果当作完成。
- 显示“未保存”：完整 story 仍可阅读；先处理本地目录权限或空间，再用新 branch ID 重试。
- 更新验证失败：旧版继续可用。
- 卸载失败：人生数据不受影响。

<details>
<summary>给熟悉终端的用户：如何运行公开包自检</summary>

在公开仓库根目录运行 `python3 -m unittest discover -s tests -p 'test_*.py' -v`，再到 `web/` 运行 `node --test`。普通用户不需要执行这些命令。

</details>

## 边界

v0.2.0 不提供云同步、遥测、社交平台直发、心理治疗或确定性人生预测。WorkBuddy、Claude Code、OpenClaw 和 Hermes 可以尝试通用 Skill 安装，但尚未列入正式支持范围。
