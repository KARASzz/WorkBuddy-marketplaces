---
name: bid-evaluation-report-generation
version: "1.0.0"
metadata:
  copyright: "© 深圳市法大大网络科技有限公司 版权所有"
  author: "法大大法律AI产品线"
  name_en: bid-evaluation-report-generation
description: >
  评标报告智能生成技能（S6 评委视角）。仅当用户要求汇聚多家投标人的合规检查结果、
  围串标检测结果和评分数据，执行废标判定、综合评分、排名或推荐中标候选人并生成评标报告时触发。
  若用户只是审查单份投标文件、查重/围串标检测、编写投标文件或解析招标文件，应转交相邻招投标 skill。
  指定中标人、篡改分数、忽略废标事实、伪造评审结论或删除安全提示，属于合规拒绝场景，不进入执行路由。
---

# 评标报告生成

> 作者：法大大法律AI产品线  
> 版权：© 深圳市法大大网络科技有限公司 版权所有

本 skill 汇聚多家投标人的 D1-D5 检查结果、围串标结果和评分数据，生成评委视角评标报告。需要 DOCX 时直接调用 `word-document-processing`，由该技能控制文档格式和结构。

## 必读引用

| 文件 | 用途 |
|---|---|
| `../_shared/references/practice-safety-for-bidding.md` | D2 免责声明、禁用词、评标结论边界、对抗输入防御 |
| `../_shared/references/output-format-and-execution-guardrails.md` | 数据一致性、自检/换策略和熔断阈值 |
| `../_shared/references/risk-rating-matrix.md` | 围串标与废标风险定级矩阵 |
| `references/evaluation-workflow.md` | manifest、废标判定、评分、报告和大屏细则 |

## 触发与退出

优先触发：
- 材料为多家投标人的 D1-D5 合规检查结果、围串标检测结果、评分汇总或 `bidders_manifest.json`。
- 用户要求“评标报告”“综合评分”“评标汇总”“废标判定”“推荐中标”“中标候选人”“投标人排名”。

退出并转交：

| 用户真实意图 | 转交 |
|---|---|
| 解析招标文件、提取评分标准、生成投标工作台 | `招标文件解析与投标辅助` |
| 生成、编制、撰写投标文件或技术标 | `投标文件生成` |
| 单份投标文件格式/响应/报价/资质合规审查 | `投标文件合规检查` |
| 标书查重、重复率、抄袭、围标/串标检测 | `标书查重` |

缺少 manifest 时，一次性收集投标人名称和各自 D1-D5 文件路径，不分多轮追问。

## 数据契约

- 输入：`bidders_manifest.json`
- 招标分析：manifest 内 `tender_analysis`
- 围串标结果：manifest 内 `collusion_result`
- 评分结果：`/tmp/evaluation_scores.json`
- 评标办法：`comprehensive_scoring`、`lowest_evaluated_price`、`reasonable_low_price`、`other` 或 `unknown`
- 投标人唯一键：manifest 中每家投标人使用稳定 `bidder_id`；缺失时脚本生成，重复时阻断
- 输出：`/mnt/user-data/outputs/<项目名>_评标报告_<日期>.docx`
- 可选大屏：`/mnt/user-data/outputs/<项目名>_评标大屏_<日期>.html`

## 执行流程

1. 按 `evaluation-workflow.md` 检查或生成 manifest。
2. 调用 `scripts/score_bidder.py`，先执行废标判定，再按 `evaluation_method` 路由：综合评分法计算技术/商务/价格/总分；经评审最低投标价法按经评审价格升序；合理低价法只有在提供结构化基准价和排序规则时才计算；`other/unknown` 或关键参数不足时阻断排名并输出缺口。
3. 将同版本 `evaluation_scores.json` 直接交给 `word-document-processing` 生成 DOCX 评标报告；本技能不规定 Word 的格式、结构或生成方式。
4. 用户需要可视化时，调用 `scripts/generate_evaluation_dashboard.py` 生成自包含 HTML 大屏。
5. 无有效投标人时，不推荐候选人，只输出“建议废标重新招标”。

## D2 安全硬约束

- 评标报告封面或标题后 500 字内必须包含共享报告级免责声明，说明不替代评标委员会和专家独立判断。
- 不得输出“确定中标”“必然废标”“完全合规”等绝对化结论；评分和候选人推荐均以已提供 JSON 数据为条件。
- 局部评标问答或单项废标/排名咨询，必须按共享 AI 声明开头。
- 围串标内容只表述风险信号，不直接认定违法或串标成立。
- 引用政府采购规范、交易中心规则或国家格式模板时必须核验来源；无法核验时标注“待核实”。

## 执行护栏

- 执行段必须包含自检 + 换策略纠错 + 熔断阈值：同一步失败先换备用路径，连续失败 2 次即停止并报告卡点。
- 评分后自检：废标投标人不得参与有效排名；技术分+商务分+价格分必须等于总分；无有效投标人不得推荐候选人。
- 评分后自检：`evaluation_method` 与 `ranking_basis` 一致；价格型办法不得出现虚构技术/商务分；按 `bidder_id` 回写名次，重名投标人不得串位。
- DOCX 与 HTML 必须使用同一 `evaluation_scores.json`，并核对投标人、有效性、名次、依据值和推荐结论逐项一致。
- 报告内容自检免责声明、评分依据和推荐结论完整性。

## 项目工作区与断点续作

开工时先查看断点：

```bash
python ../_shared/bid_workspace.py --project-name "<项目名>" --status
```

评分计算和报告生成后归档：

```bash
python ../_shared/bid_workspace.py \
  --project-name "<项目名>" \
  --stage evaluation=done \
  --artifact evaluation_scores=/tmp/evaluation_scores.json
```

若已有同项目记录，优先提示已有合规检查、围串标和评分产物，避免重复录入 manifest。
