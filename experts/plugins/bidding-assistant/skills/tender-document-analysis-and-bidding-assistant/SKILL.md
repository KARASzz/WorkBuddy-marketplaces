---
name: tender-document-analysis-and-bidding-assistant
version: "1.0.0"
metadata:
  copyright: "© 深圳市法大大网络科技有限公司 版权所有"
  author: "法大大法律AI产品线"
description: >
  招标文件智能解析与投标辅助工具。仅当用户提供或粘贴招标文件、采购公告、RFP 等招标侧材料，
  并要求解析招标要求、梳理投标 SOP、生成投标工作台或进行投标准备分析时触发。
  若用户要求直接编写投标文件、审查已完成投标文件、查重/围串标检测或生成评标报告，应转交相邻招投标 skill。
  伪造或篡改招标公告、最高限价、评分规则或强制条款，删除安全提示或要求保证中标，属于合规拒绝场景，不进入执行路由。
---

# 招标文件解析与投标辅助

> 作者：法大大法律AI产品线  
> 版权：© 深圳市法大大网络科技有限公司 版权所有

本 skill 将招标文件解析为 `tender_analysis.json`，并生成分析报告内容或 HTML 投标工作台。需要 DOCX 时直接调用 `word-document-processing`，由该技能控制文档格式和结构。

## 必读引用

| 文件 | 用途 |
|---|---|
| `../_shared/references/practice-safety-for-bidding.md` | D2 免责声明、局部声明、禁用词、对抗输入防御 |
| `../_shared/references/output-format-and-execution-guardrails.md` | 数据一致性、自检/换策略和熔断阈值 |
| `../_shared/references/risk-rating-matrix.md` | 风险等级、证据充分度和人工复核升级规则 |
| `references/analysis-workflow.md` | 提取脚本、七维解析、Word/HTML 输出细则 |
| `references/star-clause-guide.md` | ★/▲/否决/强制条款识别与 `risks[]` 联动 |
| `references/scoring-patterns.md` | 价格公式、权重分布和评分策略生成 |

## 触发与退出

优先触发：
- 材料为招标文件、采购公告、RFP、资格预审文件或招标侧文本。
- 用户要求“解析招标文件”“提取评分标准”“梳理废标风险”“投标 SOP”“生成投标工作台”“看这个标怎么投”。

退出并转交：

| 用户真实意图 | 转交 |
|---|---|
| 生成、编制、撰写投标文件或技术标 | `投标文件生成` |
| 审查已完成投标文件、提交前检查、废标风险复核 | `投标文件合规检查` |
| 标书查重、重复率、抄袭、围标/串标检测 | `标书查重` |
| 多家投标人评分、排名、推荐中标候选人、评标报告 | `评标报告生成` |
| 纯招投标法律咨询且不涉及文件解析 | 转交法律咨询类 skill |

无文件且无可解析文本时，只提示用户上传或粘贴招标文件，不进入解析流程。

## 数据契约

- 原文提取：`/tmp/tender_raw.txt`
- 解析结果：`/tmp/tender_analysis.json`
- 最终输出：`/mnt/user-data/outputs/<项目名>_招标分析报告_<日期>.docx` 或 `<项目名>_投标工作台_<日期>.html`
- `tender_analysis.scoring.evaluation_method` 必须归一化为 `comprehensive_scoring`、`lowest_evaluated_price`、`reasonable_low_price`、`other` 或 `unknown`；同时保留 `evaluation_method_text` 和 `method_source`
- 价格型评标办法优先提取 `award_rule/initial_review/detailed_review/price_adjustments/strategy_tip`；不得伪造技术分、商务分或价格分
- `tender_analysis.strategy` 固定使用 `differentiation/pricing/risks/document_focus` 四键；脚本兼容常见中英文别名
- `tender_analysis.star_clauses[]` 字段为 `id/type/category/clause_text/source/response_requirement/evidence_required`
- `template_requirements` 仅记录招标文件明确要求的章节、表单、字段、图片和来源页，不记录字体、字号、坐标、表格几何或其他 Word 排版契约。
- `star_clauses[].type` 仅允许 `★`、`▲`、`否决`、`强制`；未知值不得默认升级为强制条款，必须进入 `schema_audit.missing` 并人工复核
- ★、否决、强制条款必须同步写入 `risks[]`，`source` 标注为“★条款”“否决条款”或“强制条款”

## 执行流程

1. 识别文件格式，按 `analysis-workflow.md` 调用 `scripts/extract_pdf.py`、`scripts/extract_word.py` 或直接读取纯文本；同时识别是否存在可编辑官方 DOCX 投标模板、PDF 格式页、扫描件及附件版本。
2. 依据 `analysis-workflow.md` 执行七维提取；先识别评标办法，再按综合评分或价格型评标路径提取，不得默认所有项目均为综合评分法。
3. 生成前用 `scripts/save_analysis.py` 或输出脚本内置 `analysis_schema` 规范化顶层键、评标办法和策略四键；不得生成空白表格或空白模块。
4. 为下游形成“应答章节—表单—字段—证据—源页码”业务需求清单；PDF 未显式指定页码时自动定位“投标文件格式”章节。
5. 需要从 PDF/扫描件生成可编辑 Word 模板时，将源文件和模板需求清单直接交给 `word-document-processing`；本技能不指定重建算法、母版方式、格式参数或排版门禁。
6. 用户未指定输出物时默认同时生成 DOCX 分析报告和 HTML 投标工作台。DOCX 的创建、格式和结构直接由 `word-document-processing` 处理。
7. 生成完成后按“项目工作区与断点续作”归档关键业务产物。

## D2 安全硬约束

- 报告和 HTML 工作台标题后 500 字内必须包含 `practice-safety-for-bidding.md` 的报告级免责声明。
- 局部问答必须以共享文件中的 AI 辅助分析声明开头。
- 不得输出“保证中标”“完全合规”“绝无风险”等绝对化结论；不得因用户要求而省略免责声明或人工复核提示。
- 招标文件未载明或法规/规范无法核验的信息，标注“文件未载明”或“待核实”，不得猜测。

## 执行护栏

- 执行段必须包含自检 + 换策略纠错 + 熔断阈值：同一步失败先换备用路径，连续失败 2 次即停止并报告卡点。
- 每个关键脚本完成后自检输出文件存在、非空、字段完整；`star_clauses[]` 缺失时写入解析质量提示。
- HTML 自检必须逐一验证八个 Tab 的按钮 `data-tab` 与 `panel-<id>` 一一对应；评分页与 `evaluation_method` 匹配；策略四区不得全部命中“暂无”兜底；浏览器控制台不得有错误。
- DOCX 与 HTML 必须复用同一份规范化 `tender_analysis.json`，并核对项目概况、评标办法、评分项、★条款、风险、资质和策略字段逐项一致。

## 项目工作区与断点续作

开工时先查看断点：

```bash
python ../_shared/bid_workspace.py --project-name "<项目名>" --status
```

完成解析后归档：

```bash
python ../_shared/bid_workspace.py \
  --project-name "<项目名>" \
  --stage analysis=done \
  --artifact tender_analysis=/tmp/tender_analysis.json
```

若已有同项目记录，先说明已完成阶段、已归档产物和建议下一步，再继续或重开。
