# Prompt：分支模拟器

基于 Life World Model 和 checkout 节点模拟人生 branch。

## 输入

- base commit
- alternative choice
- Character Layer
- World Layer
- Memory Layer
- Event Graph

## 规则

- 先列 unchanged constraints，再写 branch。
- 每个结果都标注 certainty：`high_certainty` / `medium_possibility` / `low_certainty_imagination`。
- 不让人物突然变成另一个人。
- 不改变重大公共事件。
- 不把模拟当建议；最后只输出一个小行动。

## 输出

使用 `formats/branch-diff.md`。
