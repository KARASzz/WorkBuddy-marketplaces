# 标书查重与围串标工作流细则

## 1. 输入

- 单份投标文件：执行 L1-L3 查重。
- 多份投标文件且为评委/招标方视角：额外执行 L4-L6 围串标风险识别。
- 对比库目录可选；无对比库时跳过跨文档查重并在报告注明。

## 2. 文本提取

- 主文件：`scripts/extract_text.py "<bid_file_path>" --output /tmp/dedup_main.txt --structure /tmp/dedup_structure.json`
- 对比库：`scripts/extract_text.py "<corpus_dir>" --batch --output-dir /tmp/dedup_corpus/`
- 扫描件或图片 PDF 走 OCR 降级；仍失败时提示提供可编辑版本。

## 3. 三层查重

运行 `scripts/check_dedup.py --main /tmp/dedup_main.txt --structure /tmp/dedup_structure.json --corpus /tmp/dedup_corpus/ --config resources/dedup_config.json --boilerplate resources/boilerplate_phrases.json --output /tmp/dedup_result.json`。

- L1 跨文档查重：SimHash 全文指纹 + 段落级比对。
- L2 内部段落查重：字符 3-gram Jaccard。
- L3 模板套话扫描：匹配常见政府采购模板短语。

## 4. 三层围串标识别

运行 `scripts/check_collusion.py "<bid1>" "<bid2>" ... --output /tmp/collusion_result.json`。

- L4 同错性：共同错别字、标点、空格等异常。
- L5 报价规律：等差、等比、变异系数。
- L6 Word 元数据：作者、最后修改人、创建时间、模板来源。

围串标输出只表述“风险信号/疑似线索”，不得直接认定违法或串标成立。

## 5. 报告与自检

- 查重报告：将查重结果直接交给 `word-document-processing` 生成 DOCX。
- 围串标报告：将围串标结果直接交给 `word-document-processing` 生成 DOCX。
- 两类报告的格式和结构均由 Word 技能控制；本技能只保证业务数据、证据片段和风险表述准确。
- 报告标题下方写 AI 免责声明。

查重报告固定章节：项目与文件概况、综合查重率、L1 跨文档结果、L2 内部重复、L3 模板套话、证据片段、整改清单、方法与阈值说明。

围串标风险报告固定章节：项目概况、综合风险等级、L4 同错性、L5 报价规律、L6 元数据、证据线索汇总、人工核验建议、方法与限制。

## 6. 风险定级

- 查重率 `>= 40%` 为高风险、`>= 20%` 且 `< 40%` 为中风险、低于 `20%` 为低风险；同时披露 L1-L3 构成和配置阈值。
- 围串标综合风险沿用 `check_collusion.py` 的 L4/L5/L6 加权分，并按共享 `risk-rating-matrix.md` 复核影响、可能性和证据充分度。
- 仅有 B/C 级证据时不得直接作侵权、串标或违法认定。
