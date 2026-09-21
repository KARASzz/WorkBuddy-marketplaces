---
name: bid-evaluation
description: "Transform a stated tender evaluation method into a traceable scoring matrix and perform limited, document-grounded simulation or comparison. Use when the user asks to interpret evaluation criteria, calculate an explicit price formula, conduct a mock review of their materials, or compare multiple bidder documents they are authorized to provide."
---

# bid-evaluation

仅模拟招标文件明示的标准和用户有权提供的材料；不模仿评委主观偏好，不推断竞争对手非公开信息，不承诺中标或最终得分。

## 强制解析门禁

对当前会话中尚未建立有效解析证据的评标办法、招标文件、投标文件、报价表及证明材料，先调用 WorkBuddy `xparse-parse`。已有足够 Markdown/JSON 的文件直接复用；价格表、评分表、参数表或需比较的多份表格仅在尚无结构化结果时补充 JSON。

所有 WorkBuddy CLI 调用均使用 `xparse-cli --profile workbuddy`，遵循 Connector 的 task context、免费优先、PDF 输出目录和付费授权边界。解析不完整或未取得完整评标办法时，停止计算并说明不能建模的规则。

执行 `../shared/references/xparse-workbuddy-execution.md`：连接器负责 CLI；Windows 原样使用附件路径；先 `get_doc_info`，再以完整 `parse --api auto` 建立缓存；不得猜路径、扫描目录、手工拆页或假定 `ensure_parsed` 存在。

涉及投标主体、签署、证书/证件号、报价金额、日期或账号的比较和计算，按 `../shared/references/critical-field-verification.md` 先核验关键字符和页面；低可信 OCR 不得进入评分输入或多家比较结论。

## 工作流程

1. **确认评审制度和完整规则**：识别项目类型；确认评标方法、资格/符合性前置条件、评分项目、权重、上限、证据、价格公式、有效报价定义、修正/舍入规则、并列规则。仅凭“综合评分法”字样不得自行补齐公式。
2. **建立评分模型**：每一项标注为资格门槛、符合性门槛、客观评分、主观评分或价格评分。资格项不可与评分项混算；未明示的指标不得加入模型。
3. **核验输入材料**：对每位投标人建立独立证据包。缺少材料时标为“不可评分/待核验”，不能按零分、满分或默认满足处理，除非文件明确规定。
4. **客观项计算**：只在条件、单项分、上限和证据均完整时计算。显示公式、输入值、分步结果、取整方式和证据位置。
5. **价格项计算**：仅使用招标文件明确的评标基准价算法和价格公式。政府采购货物/服务项目的价格规则与工程或其他招投标项目可能不同，绝不套用“平均价/去极值/下浮系数”等网络通用算法。
6. **主观项审阅**：不替代评委打分。改为输出“评分依据覆盖度、证据充分度、文件明确的评分要素、可优化材料位置”，必要时给出非承诺性的情景区间，并清楚写明假设。
7. **多家比较**：只比较用户合法提供的材料；每家适用相同的文件标准，信息缺失保持“未知”。不提供竞争对手报价推断、围标建议或针对特定评委的策略。

## 输出：评标办法解析 / 模拟评审报告

- 规则完整性与适用范围。
- 评审流程图：资格 → 符合性 → 客观评分 → 主观评分 → 价格/排名（仅按文件实际规定）。
- 评分矩阵：`评分项｜类别｜文件规则｜所需证据｜可否计算｜计算/覆盖结果｜证据位置｜限制`。
- 客观计算明细与价格公式复核。
- 主观项依据充分度和优化建议（不等同实际得分）。
- 多家对比（如适用）与待核验项。

默认直接在对话中输出本报告；只有用户明确要求导出时才生成 HTML 或其他文件。

## 参考资料

- `../shared/references/expert-baseline.md`
- `../shared/references/xparse-workbuddy-execution.md`
- `../shared/references/critical-field-verification.md`
- `../shared/references/evaluation-rules.md`
- `../shared/references/rules-and-boundaries.md`
- `../shared/references/output-templates.md`
