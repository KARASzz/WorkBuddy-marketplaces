---
name: bid-document-generation
version: "1.0.0"
metadata:
  copyright: "© 深圳市法大大网络科技有限公司 版权所有"
  author: "法大大法律AI产品线"
description: >
  投标文件生成技能。仅当用户要求基于招标文件解析结果、招标要求或企业资料生成/编制/撰写投标文件、
  技术标、商务标、技术/商务偏离表、投标方案正文或生成前十五项质量自检时触发；优先复用 tender_analysis.json 和企业资料库。
  若用户只是解析招标文件、审查已完成投标文件、查重/围串标检测或生成评标报告，应转交相邻招投标 skill。
  伪造资质、业绩、证书、签章或授权，删除安全提示或要求跳过强制提交条件，属于合规拒绝场景，不进入执行路由。
---

# 投标文件生成

> 作者：法大大法律AI产品线  
> 版权：© 深圳市法大大网络科技有限公司 版权所有

本 skill 基于 `tender_analysis.json` 和企业资料生成评分驱动的投标业务内容。DOCX 的创建、格式和文档结构直接由 `word-document-processing` 控制，本技能不规定 Word 实现方式或深度排版门禁。

## 必读引用

| 文件 | 用途 |
|---|---|
| `../_shared/references/practice-safety-for-bidding.md` | D2 安全边界、禁用词、对抗输入防御 |
| `../_shared/references/output-format-and-execution-guardrails.md` | 数据一致性、自检/换策略和熔断阈值 |
| `references/generation-workflow.md` | 企业资料、目录、正文、组装流程 |
| `references/technical-writing-patterns.md` | 技术方案十节骨架、响应总述、服务承诺和量化承诺 |
| `references/business-doc-suite.md` | 商务十二件套、组合拳、缺料占位 |
| `references/navigation-tables.md` | 三张导航表和★条款响应对照表 |
| `references/bid-quality-preflight.md` | BQ01-BQ15 编制自检、质量台账与 Word 技能交接规则 |

## 触发与退出

优先触发：
- 材料为 `tender_analysis.json`、招标要求、企业资质/业绩资料或投标素材。
- 用户要求“生成投标文件”“写标书”“编制投标文件”“生成技术标/商务标”“根据评分项写响应章节”。

退出并转交：

| 用户真实意图 | 转交 |
|---|---|
| 解析招标文件、提取评分标准、生成投标工作台 | `招标文件解析与投标辅助` |
| 审查已完成投标文件、格式/响应/资质/报价检查 | `投标文件合规检查` |
| 标书查重、重复率、抄袭、围标/串标检测 | `标书查重` |
| 多家投标人评分、排名、推荐中标候选人、评标报告 | `评标报告生成` |

缺少招标要求时，提示先运行解析 skill 或提供招标文件；缺少企业资料时一次性列出缺口。

## 数据契约

- 输入优先级：`/tmp/tender_analysis.json` > 招标文件原件 > 用户粘贴要求。
- 企业资料：`/tmp/company_profile.json`
- 目录：`/tmp/bid_outline.json`
- 章节正文：`/tmp/bid_sections/`
- 输出：`/mnt/user-data/outputs/<项目名>_投标文件_<日期>.docx`
- 可选参考文件：招标方提供的 DOCX/PDF 格式文件、企业素材和用户指定图片目录
- 响应索引映射：`/tmp/response_index_map.json`
- 原子偏离要求与投标响应：`deviation_requirements.technical/commercial`、`/tmp/deviation_responses.json`
- 原子化偏离表：`/tmp/deviation_tables.json`（存在 blocker 或 `ok=false` 时不得组装）
- 十五项质量台账：`/tmp/bid_quality_manifest.json`
- 新增中间产物语义：`star_clause_response_table`、`navigation_tables`、`business_doc_suite_status`

## 执行流程

1. 用 `scripts/load_company_profile.py` 检查或保存企业资料；不得编造资质、业绩、人员或证书编号。
2. 读取招标分析、招标方格式文件和企业资料，提取必须响应的章节、表单、评分项和素材需求，作为结构化业务输入交给 Word 技能。
3. 按 `generation-workflow.md` 和 `technical-writing-patterns.md` 生成评分驱动内容目录；每个评分项至少一个响应章节。
4. 逐节生成正文，关键章节 800-1500 字，辅助章节 300-600 字；关键参数与招标原文一致。
5. 运行 `scripts/build_deviation_tables.py`：把技术参数和商务条款拆为原子要求，一条要求对应一行；响应必须写明具体参数、数值、单位、期限和起算条件。仅写“完全响应/完全满足/无偏离”或缺少关键要素时列为 P0，`ok=false` 不得组装。
6. 按 `business-doc-suite.md` 生成商务材料内容；缺少真实值时写入独立缺料清单，不得编造。
7. 按 `navigation-tables.md` 生成响应索引、应答表和 ★条款响应对照表的结构化数据；表格不得只有表头或空白行。
8. 按 `bid-quality-preflight.md` 执行 BQ01-BQ15 编制自检并生成 `/tmp/bid_quality_manifest.json`；内容、证据、引用、占位、承诺、日期、脱敏和签章目标由本技能负责，图表编号、表格、分页、目录及可见文本格式只形成 Word 技能的检查与修复要求。
9. 将招标方格式文件、章节内容、表格数据、企业材料、指定图片目录和质量台账直接交给 `word-document-processing` 生成 DOCX；字体、字号、目录、分页、表格、填空项、勾选项、图片、页码及其他 Word 格式和结构均由 Word 技能处理。
10. 生成后核对业务数据、项目口径、P0、未关闭占位和十五项台账状态，并提交独立合规审查；本技能不运行 DOCX 深度排版、模板血缘、格式保真或发布门禁。

## D2 安全硬约束

- 正式投标文件正文不插入 AI 免责声明；完成提示必须说明“需人工复核、签章并抽查自动回填页码后提交”。
- 用户要求编造资料、跳过签章/页码/保证金/★条款响应时，必须拒绝并列入缺口或整改清单。
- 不得承诺中标、不得保证完全合规、不得替代投标决策；相关局部问答按共享 AI 声明开头。
- 法规、交易中心规则、资质有效性无法核验时标注“待核实”。

## 执行护栏

- 执行段必须包含自检 + 换策略纠错 + 熔断阈值：同一步失败先换备用路径，连续失败 2 次即停止并报告卡点。
- 生成后自检评分项覆盖率、★响应对照表、响应索引数据、商务材料状态、报价是否超限、图片来源和 `bid_quality_manifest.json` 完整性。
- 偏离表自检原子要求数与独立响应行数一致；响应列不得只有泛化结论，`deviation_tables.json` 必须 `ok=true`。
- 候选终稿不得残留未关闭占位符；缺少真实信息、签章动作或脱敏依据不明确时必须阻断并转人工，不得猜测填充。

## 项目工作区与断点续作

开工时先查看断点：

```bash
python ../_shared/bid_workspace.py --project-name "<项目名>" --status
```

目录、章节或成品生成后归档：

```bash
python ../_shared/bid_workspace.py \
  --project-name "<项目名>" \
  --stage generation=done \
  --artifact bid_outline=/tmp/bid_outline.json \
  --artifact bid_sections=/tmp/bid_sections
```

若已有同项目记录，优先复用已归档的 `tender_analysis.json`、`bid_outline.json` 和 `bid_sections/`。
