---
name: bid-retrospective
description: Use when a bid result, score, ranking, competitor outcome, evaluator comment, loss reason, or reusable project lesson must be recorded and written back to the knowledge base.
version: "2.0.0"
category: bidding
---

# 投标复盘与知识回写

## 使用前读取

- `references/result-fields.md`
- `references/knowledge-writeback.md`
- 输出使用 `templates/retrospective-report.md`

## 输入

读取项目状态台账、最终 Markdown/Word 记录、最终报价和用户提供的结果。结果缺失时保留空缺，不根据传闻或公开排名猜测评分明细。

## 复盘步骤

1. 固定结果来源、发布日期和事实状态。
2. 对比目标、实际排名、报价和各评分项得分。
3. 把失分拆为资格/否决、价格、商务、技术、证据、表达、格式、流程和外部不确定因素。
4. 区分根因、表面现象和无法证实的假设。
5. 为每个可控问题给出责任、动作、截止时间和验证方式。
6. 识别本项目新形成且已经核验的可复用证据、模块和检查规则。
7. 按知识回写规则更新复盘档案和素材经验库，不覆盖原始文件。

## 规律升级

单一项目只形成“观察”。多个可比项目出现一致结果，或存在明确评分/制度依据时，才可形成“候选规律”；记录样本、反例、适用条件和证据强度。不得把中标等同于所有材料有效，也不得把未中标简单归因于文案质量。

## 输出

- `复盘档案/{年份-项目名称}/{项目简称}-投标结果记录-{YYYYMMDD}.md`
- `复盘档案/{年份-项目名称}/{项目简称}-投标复盘报告-{YYYYMMDD}.md`
- 经确认的素材库增量与索引更新记录。

知识回写涉及覆盖或移动文件时，先请求用户批准；优先新增版本。
