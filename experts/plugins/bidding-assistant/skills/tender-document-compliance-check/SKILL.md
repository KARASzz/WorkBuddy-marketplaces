---
name: tender-document-compliance-check
version: "1.0.0"
metadata:
  copyright: "© 深圳市法大大网络科技有限公司 版权所有"
  author: "法大大法律AI产品线"
description: >
  投标文件多维度合规检查技能。仅当用户提供已生成的投标文件，并要求提交前审查、合规检查、
  标书评审、自查自纠、编写规范性、有效应答性、技术/商务偏离表逐条审查、风险识别、废标风险排查或报价/资质/格式核验时触发；需结合 tender_analysis.json
  或要求检查应答完整性、原文一致、图号证据、交叉引用、图表编号、占位、空标题、脱敏、表格、分页、目录、标点、承诺、日期、签章页时触发；需结合 tender_analysis.json
  或招标文件原件形成检查依据。若用户只是解析招标文件、编写投标文件、查重/围串标检测或评标排名，应转交相邻招投标 skill。
  篡改报价或资质、代签代交、删除人工复核提示或要求输出“完全合规”，属于合规拒绝场景，不进入执行路由。
---

# 投标文件合规检查

> 作者：法大大法律AI产品线  
> 版权：© 深圳市法大大网络科技有限公司 版权所有

本 skill 对已编制投标文件进行提交前评审，输出“编写规范性—有效应答性—风险识别”三维审查和自查整改方案，并保留原 D1-D5 明细。

## 必读引用

| 文件 | 用途 |
|---|---|
| `../_shared/references/practice-safety-for-bidding.md` | D2 免责声明、局部声明、禁用词、对抗输入防御 |
| `../_shared/references/output-format-and-execution-guardrails.md` | 数据一致性、自检/换策略和熔断阈值 |
| `../_shared/references/risk-rating-matrix.md` | 废标、扣分、提醒风险定级与证据要求 |
| `references/compliance-workflow.md` | 投标文件提取、D1-D5 检查和报告细则 |
| `references/three-dimension-review-rules.md` | W01-W08、E01-E06、风险归并与 P0/P1/P2 整改规则 |
| `references/fifteen-quality-rules.md` | BQ01-BQ15、双页码定位、责任分流与两轮复验规则 |

## 触发与退出

优先触发：
- 材料为已完成或接近完成的投标文件、技术标、商务标、报价文件。
- 用户要求“合规检查”“标书审查/评审”“投标人自查自纠”“编写规范性”“有效应答性”“风险识别”“废标风险排查”。

退出并转交：

| 用户真实意图 | 转交 |
|---|---|
| 解析招标文件、提取评分标准、生成投标工作台 | `招标文件解析与投标辅助` |
| 生成、编制、撰写投标文件或技术标 | `投标文件生成` |
| 标书查重、重复率、抄袭、围标/串标检测 | `标书查重` |
| 多家投标人评分、排名、推荐中标候选人、评标报告 | `评标报告生成` |

缺投标文件时请求上传；缺招标要求时请求 `tender_analysis.json` 或招标文件原件。用户确认无法提供时，仅执行可独立检查项并在报告中注明跳过原因。

## 数据契约

- 投标全文：`/tmp/bid_raw.txt`
- 文档结构：`/tmp/bid_structure.json`
- 招标要求：`/tmp/tender_analysis.json` 或 `/tmp/requirements.json`
- 检查结果：`/tmp/d1_result.json` 至 `/tmp/d5_result.json`
- 三维审查结果：`/tmp/bid_review_result.json`
- 技术/商务偏离表专项审查：`/tmp/deviation_review_result.json`
- 十五项质量审查：`/tmp/bid_quality_review.json`
- 定点整改计划：`/tmp/bid_repair_plan.json`
- 输出：`/mnt/user-data/outputs/<项目名>_投标文件审查与自查整改报告_<日期>.docx`

## 执行流程

1. 按 `compliance-workflow.md` 提取投标文件；扫描件或图片 PDF 正文不足 500 字时使用 OCR 降级。
2. 优先读取 `tender_analysis.json`，显式加载 `risks[]`、`star_clauses[]`、强制资质、评分、商务要求、时间节点。
3. 依次执行 D1 格式、D2 实质性响应、D3 废标风险与★条款、D4 报价、D5 资质完整性检查脚本。
4. 运行 `scripts/check_deviation_tables.py`：把技术/商务要求原子化并与偏离表逐行配对；一行合并多条要求、遗漏响应、仅写“完全响应/完全满足/无偏离”或缺少数值/单位/期限/起算点时直接列为 P0。
5. 按 `fifteen-quality-rules.md` 对最终版面执行 BQ01-BQ15；无最终物理页码时不得判定通过，先调用 `word-document-processing` 生成或渲染当前版本后再审查。
6. 生成 `/tmp/bid_quality_review.json`。每个失败项记录规则、风险、物理 PDF 页、显示页码、章节、文字锚点、问题证据、期望状态、具体修改方法和复验条件；证据不足不得默认通过。
7. 归并编写规范性、E01-E06 有效应答性、BQ01-BQ15 和风险识别；生成 `/tmp/bid_repair_plan.json`，将内容类问题退回投标文件生成，将图表编号、表格、分页、目录和可见文本格式交给 `word-document-processing`，将缺真实信息、签章动作或脱敏依据不明项转人工。
8. 生成 P0/P1/P2、责任人和完成时点的优化方案；★/否决/强制条款未规避项、明确废标风险、E05/E06 偏离表缺口和候选终稿占位必须在 P0 置顶。风险等级只能基于招标后果和实际影响，不因 BQ 编号固定放大。
9. 将同版本 `bid_review_result.json`、`bid_quality_review.json` 和 D1-D5 直接交给 `word-document-processing` 生成 DOCX 报告；本技能不规定 Word 的格式、结构或生成方式。

## D2 安全硬约束

- 报告标题下方 500 字内必须包含共享报告级免责声明，并提示人工复核后使用。
- 局部检查问答按共享 AI 声明开头。
- 不得输出“完全合规”“绝无废标风险”等绝对化结论；不得因用户要求而删除人工复核提示。
- 无法在投标文件中找到对应内容时，统一写“未找到对应表述，建议人工核查”，不得推断性判定。
- D2 规则模式提取不到关键词时必须输出“待人工核查”，不得默认“完全响应”。

## 执行护栏

- 执行段必须包含自检 + 换策略纠错 + 熔断阈值：同一步失败先换备用路径，连续失败 2 次即停止并报告卡点。
- 报告内容生成后自检三维正文、D1-D5 附录、D3 ★条款行和 P0/P1/P2 排序。
- 校验 `bid_quality_review.json` 必须且仅含 BQ01-BQ15；所有失败项均有双页码、锚点、可执行整改和复验条件。
- 版面类问题只给 Word 技能下达验收与修复要求，不在本技能中写入或重排 DOCX。

## 项目工作区与断点续作

开工时先查看断点：

```bash
python ../_shared/bid_workspace.py --project-name "<项目名>" --status
```

五维检查完成后归档：

```bash
python ../_shared/bid_workspace.py \
  --project-name "<项目名>" \
  --stage compliance=done \
  --artifact d1=/tmp/d1_result.json \
  --artifact d2=/tmp/d2_result.json \
  --artifact d3=/tmp/d3_result.json \
  --artifact d4=/tmp/d4_result.json \
  --artifact d5=/tmp/d5_result.json \
  --artifact deviation_review=/tmp/deviation_review_result.json \
  --artifact bid_review=/tmp/bid_review_result.json \
  --artifact bid_quality_review=/tmp/bid_quality_review.json \
  --artifact bid_repair_plan=/tmp/bid_repair_plan.json
```

若已有同项目记录，优先复用已归档的招标分析与历史检查结果，并提示是否重新检查。
