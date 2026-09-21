# 招标文件解析工作流细则

## 1. 输入与提取

- PDF：`python scripts/extract_pdf.py "<文件路径>" --output /tmp/tender_raw.txt`
- Word：`python scripts/extract_word.py "<文件路径>" --output /tmp/tender_raw.txt`
- 纯文本：直接读取。
- 提取失败或正文不足 200 字时，请用户补充文本或换格式。

## 2. 七维提取

输出统一写入 `tender_analysis`：

1. `project_overview`：项目名称、招标人、预算、期限、地点、背景。
2. `dates`：报名、答疑、踏勘、递交、开标、公示、合同签订等时间节点。
3. `qualifications`：强制资质和加分资质，保留证明材料与出处。
4. `scoring`：先识别 `evaluation_method`，再按 `scoring-patterns.md` 路由：综合评分法提取技术/商务/价格分；经评审最低投标价法或合理低价法提取中标规则、评审阶段和价格规则。不得为价格型评标办法虚构分值。
5. `risks`：废标风险、来源条款、等级、规避措施。
6. `commercial`：保证金、限价、有效期、付款、验收、质保、分包限制。
7. `star_clauses`：按 `star-clause-guide.md` 识别 ★/▲/否决/强制条款；★、否决、强制条款同步进入 `risks[]`。

另生成 `strategy` 四个固定字段：`differentiation/pricing/risks/document_focus`。内容可为字符串或列表；不得改用 `key_points/strengths/weaknesses/actions` 等自由键名。

## 3. 输出结构

先用 `scripts/save_analysis.py` 或输出脚本内置 `analysis_schema` 规范化键名，避免空白模块。

- DOCX：将规范化 `tender_analysis.json` 直接交给 `word-document-processing`，由其决定报告格式和结构；报告内容包含项目概况、时间节点、资质、评分、★条款、废标风险、商务摘要和投标策略。
- HTML：`scripts/generate_html_workbench.py`，包含总览、时间轴、评分拆解、风险雷达、资质清单、SOP、策略备忘录。

## 4. 自检重点

- `star_clauses[]` 存在；缺失时写解析质量提示。
- ★/否决/强制条款已同步到 `risks[]`，`source` 为“★条款/否决条款/强制条款”。
- DOCX/HTML 的业务模块均应有实际内容，缺失信息明确标注待核实。
- 评分分值合计异常时提示人工核实。
- `scoring.evaluation_method` 与评分页模板一致；价格型评标办法无技术评分项时不应报“评分页为空”。
- `strategy` 四区至少有一项实质内容；若原文或企业能力信息不足，明确列出待补信息，不用空字符串。
- HTML 八个 Tab 的 `data-tab` 与 `panel-<id>` 一一对应，并在真实浏览器中逐一点击验证。
