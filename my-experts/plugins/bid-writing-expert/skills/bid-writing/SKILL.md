---
name: bid-writing
description: 标书制作辅助技能：提供投标文件标准结构规范、投标结果复盘字段规范，以及招标解析报告与复盘报告模板。供标书制作专家在分阶段制作与复盘迭代时调用。
---

# 标书制作辅助 Skill

为「标标」提供结构规范、字段规范和文档模板。

## 使用方式

| 场景 | 读取文件 |
|------|----------|
| Phase 0 撰写《招标解析报告》 | `templates/bid-analysis-report.md` |
| Phase 2 分册制作（确认各册章节结构） | `references/bid-structure.md` |
| 复盘时录入投标结果字段 | `references/retrospective-fields.md` |
| 生成《投标复盘报告》 | `templates/retrospective-report.md` |

## 规则

1. 复盘结果字段以 `references/retrospective-fields.md` 为准，用户未提供的字段标注"待补充"，不得编造
2. 分册章节结构以 `references/bid-structure.md` 为基准，按具体招标文件要求增删，增删处需向用户说明
3. 模板中的 `{{占位符}}` 必须替换为实际内容，交付前检查无残留占位符
