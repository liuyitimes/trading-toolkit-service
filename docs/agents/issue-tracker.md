# 问题跟踪

本仓库的问题和规格以 Markdown 文件形式存放在 `.scratch/`。

## 存放约定

- 每个功能使用一个目录：`.scratch/<feature-slug>/`。
- 功能规格文件为 `.scratch/<feature-slug>/spec.md`。
- 实施问题按单个任务存放：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`，编号从 `01` 开始。
- 每个问题文件开头附近使用 `Status:` 行记录分诊状态。
- 评论与会话历史追加在文件末尾的 `## Comments` 标题下。

## 技能操作

当技能要求“发布到问题跟踪器”时，在 `.scratch/<feature-slug>/` 下新建文件；目录不存在时先创建目录。

当技能要求“获取相关任务”时，读取引用路径对应的文件。用户通常会直接提供文件路径或问题编号。

## 路线图操作

`wayfinder` 使用一份路线图文件和每个任务对应的一份子文件。

- 路线图：`.scratch/<effort>/map.md`。
- 子任务：`.scratch/<effort>/issues/NN-<slug>.md`，编号从 `01` 开始，文件包含 `Type:` 与 `Status:` 行。
- 阻塞关系：在文件开头附近使用 `Blocked by: NN, NN` 行；列出的所有任务解决后，当前任务解除阻塞。
- 待领取任务：扫描 `.scratch/<effort>/issues/`，选择处于开放、未阻塞且未认领状态的任务；按编号优先。
- 认领：先将 `Status:` 设为 `claimed` 并保存。
- 解决：在 `## Answer` 下追加结论，将 `Status:` 设为 `resolved`，再向路线图的决策部分追加上下文指针。
