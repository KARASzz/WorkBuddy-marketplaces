# 投标文件合规检查与三维自查工作流

## 1. 输入

- 必需：最终投标文件 DOCX/PDF。
- 必需二选一：/tmp/tender_analysis.json 或招标文件原件。
- 缺招标要求时仅执行可独立检查项并标注跳过原因。

## 2. 提取与加载

- 用 scripts/extract_bid.py 提取全文和章节结构。
- 扫描件或图片 PDF 正文不足 500 字时使用 OCR 降级。
- 最终文件为 DOCX 或 PDF 时提取其可见文本和业务结构；本技能不解析 OOXML 排版细节。
- 招标要求优先读取 tender_analysis.json；降级使用 scripts/extract_requirements.py。

## 3. 五维检查

1. D1 格式合规：scripts/check_format.py。
2. D2 实质性响应：scripts/check_response.py；复杂项目优先 --mode llm。
3. D3 废标风险与★条款：scripts/check_risk.py；未规避强制条款必须置顶。
4. D4 报价合规：scripts/check_price.py。
5. D5 资质完整性：scripts/check_qualification.py。

D2 规则模式无法提取关键词时结论为“待人工核查”，不得自动通过。

## 4. 偏离表 P0 专项审查

~~~bash
python scripts/check_deviation_tables.py \
  --requirements /tmp/tender_analysis.json \
  --bid "/path/to/final_bid.docx" \
  --output /tmp/deviation_review_result.json
~~~

脚本按“一条原子要求一行”匹配技术/商务偏离表，阻断合并响应、遗漏响应、泛化响应以及缺少具体参数、单位、期限和起算点的响应。存在 P0 时退出码为 2。

## 5. 三维自查归并

按 `three-dimension-review-rules.md` 归并业务检查结果：

- 编写规范性：招标要求的章节、表单、必填内容和附件是否齐备；
- 有效应答性：要求覆盖、实质响应、证据链和资格证明；
- 风险识别：归并 D1/D3/D4/D5 和编制风险；
- 优化建议方案：P0/P1/P2、责任人、时点、复验标准。

随后按 `fifteen-quality-rules.md` 执行 BQ01-BQ15：

- 内容、证据、引用、承诺、日期、脱敏和签章清单基于招标原文与投标可见内容核验；
- 图表编号、表格、分页、目录和可见文本格式基于 Word 技能生成的最终版面/PDF 核验；
- 物理 PDF 页码和页脚显示页码分开记录；无最终物理页码时不得给出通过；
- 输出 `/tmp/bid_quality_review.json` 与 `/tmp/bid_repair_plan.json`。

## 6. DOCX 报告

将 D1-D5、`/tmp/bid_review_result.json` 与 `/tmp/bid_quality_review.json` 直接交给 `word-document-processing` 输出 DOCX；格式和结构由 Word 技能控制。

报告正文为总览、三维总览、编写规范性、有效应答性、风险识别、优化建议方案；原 D1-D5 作为附录保留。所有★/否决/强制条款未规避项必须排在 P0 最前。

## 7. 自检重点

- 每项审查均有规则、证据、位置、风险、整改和复验标准。
- 技术/商务偏离表的原子要求数与独立响应行数一致，响应列无泛化结论；E05/E06 P0 全部清零。
- 报告含 AI 免责声明，不使用“完全合规”“绝无风险”等结论。
- BQ01-BQ15 每项均有状态和证据；失败项均有双页码、文字锚点、具体修改方法、责任分流和复验条件。
- 内容问题与版面问题分别路由；Word 技能修复输出 `_优化Vn.docx`，不得覆盖原文件。
- DOCX 的排版、表格和文档结构由 `word-document-processing` 负责，本技能不设置深度排版门禁。
