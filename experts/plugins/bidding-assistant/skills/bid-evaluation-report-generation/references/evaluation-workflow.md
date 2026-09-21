# 评标报告生成工作流细则

## 1. 输入

必需 `bidders_manifest.json`，映射招标分析、围串标结果和各投标人 D1-D5 检查结果：

```json
{
  "tender_analysis": "/path/to/tender_analysis.json",
  "collusion_result": "/path/to/collusion_result.json",
  "bidders": [
    {"name": "投标人A", "d1": "...", "d2": "...", "d3": "...", "d4": "...", "d5": "..."}
  ]
}
```

未提供 manifest 时，一次性收集投标人名称和 D1-D5 路径，生成 manifest 后继续。

## 2. 废标判定与评分

运行 `scripts/score_bidder.py --manifest /path/to/bidders_manifest.json --output /tmp/evaluation_scores.json`。

废标判定先于评分：

- D1 存在 `severity == "废标"`。
- D3 存在 `avoidance_status == "未规避"`。
- D4 最高限价检查未通过。
- D5 必要资质 `status == "未声明"`。

先读取 `tender_analysis.scoring.evaluation_method`，不得为 `unknown/other` 猜测评标公式：

- `comprehensive_scoring`：有效投标人再计算技术分、商务分、价格分和总分；权重从 `tender_analysis.scoring` 读取。
- `lowest_evaluated_price`：优先使用 manifest 的 `evaluated_price`；无价格调整规则时可使用投标报价，按经评审价格升序排列，不生成技术/商务分。
- `reasonable_low_price`：仅当 scoring 提供结构化 `benchmark_price` 和 `ranking_rule=closest_to_benchmark` 时，按与基准价偏差升序排列；否则阻断排名并输出参数缺口。
- `other/unknown`：阻断自动排名和候选人推荐，只输出已完成的资格/符合性检查及待确认事项。

manifest 中每家投标人应提供唯一 `bidder_id`。缺失时脚本按序生成；重复 ID 时停止评分。重名投标人以 `bidder_id` 区分，不得按名称回写名次。

## 3. 报告与大屏

- DOCX 报告：将 `/tmp/evaluation_scores.json` 直接交给 `word-document-processing`，由其控制报告格式和结构。
- HTML 大屏：`scripts/generate_evaluation_dashboard.py --scores /tmp/evaluation_scores.json --output ...`

报告八章：项目基本信息、开标记录、资格审查、符合性审查、详细评审、综合排名、推荐中标候选人、围串标风险附录。

## 4. 自检重点

- 报告标题或封面后 500 字内包含 AI 免责声明。
- 废标投标人不得参与有效排名。
- 技术分、商务分、价格分之和必须等于总分。
- 无有效投标人时输出“建议废标重新招标”，不得推荐候选人。
- `calculation_status=blocked` 时不得推荐候选人，报告必须列出 `calculation_warnings`。
- Word 与 HTML 从同一 `evaluation_scores.json` 生成，并核对投标人、有效性、排名依据、名次与推荐结论一致。
- docx 无 emoji，表格宽度不超过 9026 DXA，颜色使用 OOXML 样式。
- 引用政府采购规范或地方规则时必须核验来源；无法核验则标注“待核实”。
