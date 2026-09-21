---
name: bid-precheck
description: "Pre-check a bidder's documents against the tender-side requirements. Use when the user supplies a tender document together with a bid, qualification materials, certificates, response tables, price files, or evidence documents and asks for completeness, qualification, substantive-response, deviation, or consistency review."
---

# bid-precheck

这是投标前质量审阅，不是法定资格审查、符合性审查或最终废标认定。输出必须把“已证实不符”“待核验”“材料缺失”和“建议优化”分开。

## 强制解析门禁

对当前会话中尚未有有效解析证据的招标侧文件、投标文件和证明材料，先用 WorkBuddy `xparse-parse` 逐份解析。不可只凭文件名、用户描述、预览文本或经验判断；已解析且当前任务所需视图完整的文件直接复用。

- 在 WorkBuddy 使用 `xparse-cli --profile workbuddy` 和 Connector 所规定的 task-context、免费优先、付费需同意、PDF 输出目录等规则。
- 严格执行 `../shared/references/xparse-workbuddy-execution.md`：连接器负责 CLI；Windows 原样使用附件路径；先 `get_doc_info`，再以完整 `parse --api auto` 建立缓存；禁止 Git Bash 路径转换、目录扫描、手工拆页和假定 `ensure_parsed` 存在。
- 对姓名、签署、签章遮挡、证书/证件号、金额、日期、账号和型号的一致性核验，执行 `../shared/references/critical-field-verification.md`。仅凭 Markdown OCR 出现不同读法，尤其是手写签名或盖章区域，不得标为已证实不一致或高风险。
- 仅当需要新增视图/页码、文件版本变更、既有结果不完整或不可访问时，才补充或重新解析；用户追问同一份材料时先查会话证据台账。
- 资格、响应、证书、业绩、财务或签署材料若未提供、不可解析或无法从当前材料确认真实性/有效期，只能标记 `待核验`。
- 响应表、参数表、报价表、人员表、跨页证书或需定位证据的附件，使用 JSON 解析保留结构；不需要坐标/字符置信度时不要开启字符级详情。

## 前置条件

至少需要一份招标侧规则文件和一份投标侧材料。缺少招标侧文件时，只能做“投标文件内部一致性与资料完整性检查”；缺少投标侧材料时，转交 `tender-analysis`，不得声称已完成预审。

## 工作流程

1. **文件角色与版本配对**：区分招标规则、投标响应、证明材料和补遗；确认投标材料使用的是最新补遗后的规则版本。
2. **建立要求—响应—证据矩阵**：先从招标文件逐项提出要求，再寻找投标响应和证明材料。禁止先看投标材料再倒推要求。
3. **资格与材料核验**：检查主体、资质、许可、人员、业绩、财务、信用、联合体/分包及各类证明是否符合文件表面要求。对外部真实性、原件、登记/信用状态和有效期覆盖范围单独标注。
4. **符合性与偏差核验**：逐项检查实质性技术、商务、报价、投标有效期、保证金、签署/递交和格式要求。只有文件明确了实质性后果或适用规则明确时，才标为可能导致无效/否决的高风险；一般形式问题不可自动等同于无效。
5. **完整性与一致性核验**：检查必交文件、附件、签字盖章、电子文件要求（仅限文件能够证明的部分），以及项目名称、标段、主体、日期、报价、工期、人员、设备、参数、业绩在正文和附件间是否一致。先确认角色关系；可能导致高风险的关键字段必须先完成可信度与页面核验。
6. **技术/商务/价格专项检查**：技术参数要判断比较口径、单位、阈值和证明来源；商务条款要检查是否出现不可接受附加条件；报价检查仅按文件明示公式与修正规则核对，不将算术差错一概判为无效。
7. **形成整改闭环**：按截标优先级给出待补材料、需确认事实、需要修订的响应和人工复核点；已递交文件不建议通过未经许可的方式补改。

## 输出：投标文件预审报告

1. 审阅范围、文件清单、版本及解析质量。
2. 风险摘要：`🔴 高风险｜🟡 待核验/中风险｜🟢 建议优化`。
3. 主矩阵：`招标要求｜性质｜投标响应｜证明材料｜判断｜证据位置｜建议动作`。
4. 完整性清单、内部一致性冲突表、技术/商务偏差表和报价核验表（按材料适用性取用）。
5. 截标前行动清单：区分“必须核验”“必须调整”“可优化”。
6. 限制与免责声明：说明这不是正式评审结论，证书/信用/原件/签章真实性等需人工或合法渠道复核。

对 OCR 存疑的关键字段，附“OCR 初读—置信度/候选—多模态页面复核—结论”表；有字符坐标时定位到字段区域并保留必要表单上下文。不要把这类条目并入已证实风险。

默认直接在对话中输出本报告；只有用户明确要求导出时才生成 HTML 或其他文件。

## 参考资料

- `../shared/references/expert-baseline.md`
- `../shared/references/xparse-workbuddy-execution.md`
- `../shared/references/critical-field-verification.md`
- `../shared/references/bid-precheck-rules.md`
- `../shared/references/rules-and-boundaries.md`
- `../shared/references/output-templates.md`
