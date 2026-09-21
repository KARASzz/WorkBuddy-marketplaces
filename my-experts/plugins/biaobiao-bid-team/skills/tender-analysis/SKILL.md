---
name: tender-analysis
description: Use when a tender, addendum, clarification, scoring method, qualification clause, technical specification, contract term, or submission requirement must be analyzed and anchored to source text.
version: "2.1.0"
category: bidding
---

# 招标解析

## 使用前读取

- `references/analysis-checklist.md`
- 输出使用 `templates/tender-analysis-report.md`
- 矩阵使用 `templates/requirement-evidence-matrix.md`

## 执行顺序

1. 先核验收到的招标包是否完整（对照《招标包完整性核验表》），
   确认有无未到件册次；再清点正文、附件、清单、图纸、合同、格式、补遗和澄清，建立版本顺序。
   发现未到件册次，立即回报标标，不得自行以其他册次内容推定。
2. 识别采购制度和项目边界；不确定时标为待核验。
3. 先找否决条款和资格条件，再拆评分办法、技术/商务/报价要求和提交形式。
4. 正向阅读一次，按关键词和交叉引用反向核对一次。
5. 把每个要求写入矩阵，记录原文定位、风险和证据需求。
6. 对跨章节冲突、扫描模糊、公式异常和标准版本问题单独建项。

## 解释边界

招标要求与现行公开标准是两个字段。公开信息用于提示时效和合规风险，不用于无声改写招标原文。常见行业做法只能作为建议，不能作为本项目事实。

## 完成标准

- 资格、否决、评分三类条目没有只做摘要而缺少定位。
- 总分可回算，评分子项与分值能够对应。
- 关键时间同时记录日期、时间、时区/地点和来源。
- 保证金、有效期、签章、密封/上传、文件格式、份数等形式要求已覆盖。
- 所有不确定项进入待确认清单。
- 招标包全部应有册次已确认到齐；未到齐项已登记为阻塞并在报告中置顶提示。

完成后把成果交给标标请求门禁 #1，不自行进入下一阶段。
