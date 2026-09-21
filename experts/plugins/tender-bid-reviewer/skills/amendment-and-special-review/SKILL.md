---
name: amendment-and-special-review
description: "Analyse addenda, clarifications, and document versions, or perform focused tender/bid review of technical parameters, commercial contract terms, and pricing or bill-of-quantities documents. Use when the user provides original and revised documents, addenda, parameter response tables, contracts, or pricing documents and needs a traceable impact analysis."
---

# amendment-and-special-review

处理版本影响和专项高密度信息，强调“原文—修改—受影响响应—行动”的证据链。

## 强制解析门禁

所有当前会话中尚未有有效解析证据的原文件、补遗/澄清、修订版、参数表、合同或报价/工程量清单，必须先以 WorkBuddy `xparse-parse` 解析。对已解析且当前任务所需证据完整的文件复用结果；只有版本变化、缺少 JSON/页码、范围不足、结果不可访问/不完整或用户明确要求时才补充/重新解析。对表格与版本定位优先 JSON；对条款通读优先 Markdown。

在 WorkBuddy 使用 `xparse-cli --profile workbuddy`，遵循 Connector 对首次 task context、PDF 输出目录、免费优先和显式付费同意的规则。无法确认文档版本、解析不完整或缺少原件时，不把版本差异写成确定结论。

执行 `../shared/references/xparse-workbuddy-execution.md`：连接器负责 CLI；Windows 原样使用附件路径；先 `get_doc_info`，再以完整 `parse --api auto` 建立缓存；不得猜路径、扫描目录、手工拆页或假定 `ensure_parsed` 存在。

版本比对、参数/报价/合同专项中出现姓名、签署、印章遮挡文字、金额、日期、账号或型号差异时，按 `../shared/references/critical-field-verification.md` 核验；不能把低可信 OCR 差异当作版本实质变更。

## A. 补遗/澄清与版本影响

1. 按发布时间、编号、发布渠道（如文件可见）和文件角色建立版本序列；不假定“最新文件天然覆盖一切”。
2. 将每一项修改分类为：项目/日程、资格/材料、投标规则、评标规则、技术参数、商务合同、报价/清单或其他。
3. 同时列出**直接修改点**和**关联影响点**，例如参数变更可能影响响应表、产品证明、方案、报价和交付承诺。
4. 若多份文件冲突，记录冲突原文、日期/编号和文件中是否有优先级约定；没有明确依据时标记待澄清，不能机械地假设“后发文件一律优先”。
5. 输出补遗响应矩阵：`文件/编号｜原要求｜修改内容｜受影响投标文件｜必须动作｜证据位置｜待澄清`。

## B. 技术参数与响应表专项

1. 从招标参数表提取：指标、比较对象、操作符、阈值/范围、单位、强制性/评分属性、证明要求和来源。
2. 将投标响应与产品手册、检测报告、授权材料建立证据链。参数名称相似但型号、测试条件或单位不同，必须标为待核验。
3. 仅在比较口径一致时判定满足/不满足；不擅自把“优于”“等同”“兼容”等模糊词转换为数值结论。

## C. 商务/合同条件专项

提取价格类型、付款、保证金、交付/工期、验收、质保、变更、违约、责任限制、保险、分包、保密/知识产权、争议解决等。输出履约与现金流风险提示，但不输出替代法律意见或擅自起草具有法律结论的条款。

## D. 报价/工程量清单专项

1. 检查完整性、单价×数量与合价、分项合计与总价、单位/税率/暂列金额等在文件可验证范围内的一致性。
2. 仅按招标文件载明的报价规则、修正规则和价格评分公式判断；不同项目类型的规则不可互套。
3. 对明显低价只提示“可能需要成本合理性说明/人工复核”，不自行断言低于成本或恶意报价。

## 输出

按用户场景选择：

- 《补遗/版本影响清单》
- 《技术参数—响应—证据矩阵》
- 《商务合同条款审阅表》
- 《报价/工程量清单核验表》

所有输出都应包含审阅范围、版本、解析局限、证据位置、待核验项和优先行动；格式见 `../shared/references/output-templates.md`。

默认直接在对话中输出结果；只有用户明确要求导出时才生成 HTML 或其他文件。

## 参考资料

- `../shared/references/expert-baseline.md`
- `../shared/references/xparse-workbuddy-execution.md`
- `../shared/references/critical-field-verification.md`
- `../shared/references/amendment-and-special-rules.md`
- `../shared/references/rules-and-boundaries.md`
- `../shared/references/output-templates.md`
