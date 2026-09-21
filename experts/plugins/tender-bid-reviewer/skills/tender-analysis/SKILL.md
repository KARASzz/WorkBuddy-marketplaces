---
name: tender-analysis
description: "Interpret tender-side documents into a traceable tender brief, covering project scope, dates, qualification requirements, substantive-response risks, evaluation rules, technical/commercial requirements, pricing requirements, and clarification questions. Use when the user provides a tender notice, tender document, technical specification, BOQ, draft contract, or evaluation method and asks what it requires or how to prepare a compliant bid."
---

# tender-analysis

将招标侧文件从“长文档”转化为可执行、可追溯的投标准备信息。它只从文件中提取和判断，不以经验补写未出现的项目规则。

## 强制解析门禁

只要任务需要读取当前会话中尚未有有效解析证据的招标公告、招标文件、技术规范、工程量清单、合同草案、评标办法或补遗，必须先调用 WorkBuddy 的 `xparse-parse`。同一会话中已解析且证据足够的文件应复用，不得为追问重复解析。

- 在 WorkBuddy 中使用 `xparse-cli --profile workbuddy`；某一新用户请求确需解析时，其首次调用按 Connector 规则加入私有 task context。
- 严格执行 `../shared/references/xparse-workbuddy-execution.md`：连接器负责 CLI；Windows 原样使用附件路径；先 `get_doc_info`，再以完整 `parse --api auto` 建立缓存；禁止 Git Bash 路径转换、目录扫描、手工拆页和假定 `ensure_parsed` 存在。
- 涉及招标人名称、金额、日期、账号、签章或扫描件中的关键字段时，按 `../shared/references/critical-field-verification.md` 核验；低可信 OCR 不作为明确规则或冲突事实。
- 维护文件版本与解析视图台账。后续只在需要 JSON、补充页码、文件版本改变、结果不可用/不完整或用户明确要求时补充/重新解析。
- 默认 `--api auto`。PDF 必须保存至输出目录后再读取；格式、配额/页数/大小以当前服务返回为准，任何 `--api paid` 调用均须如实说明并取得用户同意。
- 先解析全文 Markdown；涉及评分表、参数表、报价/工程量清单、跨页表或页码/元素定位时，再取得 JSON。
- 解析失败、加密、缺页或结果可信度不足时，只输出“待核验/待补文件”，不得据此认定资格、响应或风险已被排除。

## 输入识别

将材料标注为：招标公告/邀请书、投标人须知及前附表、资格审查标准、评标办法、技术规范、工程量清单/报价表、合同条款、图纸/附件、澄清/补遗。缺少任何关键部分时，在结论中列为审阅盲区。

## 工作流程

1. **建立文件版本清单**：记录文件名、版本/发布日期、文档角色和解析状态；补遗单列，不与原文混写。
2. **提取项目概览与日程**：项目名称/编号/标段、采购/招标人、范围、地点、交付或工期、预算/最高限价（如明示）、投标/开标/答疑/保证金/有效期等。日期必须注明来源，不能由公告常识推算。
3. **结构化资格与文件要求**：按主体、资质许可、人员、业绩、财务、信用、联合体、分包、证明材料和签署递交拆分。将复杂句拆为时间、数量、金额/等级、对象、证据、例外和后果。
4. **识别实质性要求与风险**：优先提取文件明示的“无效、否决、不得、必须、不允许偏离、实质性”等条款，但不能只靠关键词；须同时读取条款上下文、适用对象和后果。
5. **建模评标办法**：区分资格/符合性门槛、客观评分、主观评分、价格公式、加分证据和排名规则。只使用文件明示的评分方法、有效报价范围、精度和修正规则。
6. **解读技术、商务与报价边界**：抽取技术参数、标准、验收、接口、实施/服务、付款、质保、违约、变更、分包、保密/知识产权、保险和工程量/报价口径。识别文件内部矛盾、空白或高履约风险，但不替用户作商业决策。
7. **形成澄清问题**：仅就会影响资格、报价、技术方案或履约的矛盾/模糊/遗漏问题提出具体、可定位、通过正式渠道提交的澄清问题。不得建议披露己方价格、方案或竞争信息。

## 输出：招标文件解读与投标准备报告

按以下顺序输出，详见 `../shared/references/output-templates.md`：

1. 审阅范围、文件版本和解析限制。
2. 项目概览与关键日程表。
3. 资格条件与证明材料清单。
4. 实质性要求/潜在否决风险清单：`要求｜性质｜文件后果｜证据位置｜建议动作`。
5. 评分模型与得分材料矩阵；资格项与评分项必须分开。
6. 技术、商务、报价和合同履约要点。
7. 待澄清问题、待补材料及投标准备行动清单。

所有文件事实使用 `【文件名｜章节/页码/表格】` 定位；若无法可靠定位，说明原因。结论以“明确要求”“高风险”“待核验”“建议优化”区分。

默认直接在对话中输出本报告；只有用户明确要求导出时才生成 HTML 或其他文件。

## 参考资料

- `../shared/references/expert-baseline.md`
- `../shared/references/xparse-workbuddy-execution.md`
- `../shared/references/critical-field-verification.md`
- `../shared/references/tender-analysis-rules.md`
- `../shared/references/rules-and-boundaries.md`
- `../shared/references/output-templates.md`
