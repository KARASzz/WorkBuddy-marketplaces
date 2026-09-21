---
name: final-docx-assembly
description: Use when gate 4 has been explicitly approved and WorkBuddy must turn the final approved Markdown set into one Word deliverable without changing facts or silently filling gaps.
version: "2.0.0"
category: bidding
---

# WorkBuddy 最终 Word 生成

## 使用前读取

- `references/finalization-checklist.md`
- 生成前填写 `templates/finalization-record.md`

## 硬性触发条件

只有以下条件同时成立时使用本技能：

- 用户已对明确的《合规终审报告》和最终 Markdown 清单批准门禁 #4。
- 阻断问题为零，正式价格已经确认。
- 全部输入绑定同一招标、补遗、证据和价格版本。
- 需要插入的本地图片和附件路径可访问。

任一条件不满足时停止，不生成“预览 Word”绕过门禁。

## 生成原则

1. 先填写终稿生成记录，固定输入顺序和版本。
2. 使用 WorkBuddy 当前可用的文档生成能力创建一个新的 `.docx`。
3. 以最终 Markdown 为事实与正文来源，不在转换阶段润色、改写、补数或新增承诺。
4. 保持标题层级、表格、列表、图片、附件引用和明确分页意图。
5. 不覆盖任何原始文件或已批准版本。
6. Word 生成后，继续保留 Markdown 作为可追溯底稿。

## 生成后核对

核对 Word 可打开、目录和章节顺序、标题层级、表格、图片、分页、页眉页脚、页码、附件索引、项目名称、报价、签章位以及待填标记。版式变化不能改变数字、单位、否定词、表格行列或响应含义。

## 能力不可用

如果 WorkBuddy 当前环境无法可靠创建 DOCX，明确说明限制，交付最终 Markdown 集合和生成记录，并请用户在具备文档能力的 WorkBuddy 环境继续。不得运行未知外部程序、上传商业资料或把文本文件改扩展名冒充 Word。

## 输出

- `{项目简称}-投标文件终稿-{YYYYMMDD}.docx`
- `{项目简称}-终稿生成记录-{YYYYMMDD}.md`
- `{项目简称}-递交前检查表-{YYYYMMDD}.md`
