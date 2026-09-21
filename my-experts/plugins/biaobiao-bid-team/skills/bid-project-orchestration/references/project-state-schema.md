# 项目状态台账字段

## YAML 头部

```yaml
---
project_id: 2026-项目简称
project_name: 项目全称
tender_version: v1-招标文件及补遗标识
stage: 0
gate: 0
gate_status: pending
generated_at: 2026-09-03T10:00:00+08:00
source_files:
  - 招标文件-待投标/2026-项目简称/文件名
---
```

## 台账正文必须记录

- 项目目录、项目简称、采购人/招标人、项目编号和标段。
- 招标文件、附件、图纸、清单、补遗、澄清、用户输入的版本清单。
- 当前阶段、各门禁状态、批准记录和失效记录。
- 最新要求矩阵、证据清单、商务册、技术册、价格册、终审报告的文件名。
- 阻断项、待确认项、负责人、截止时间和下一动作。
- 敏感级别和允许外发范围。

## 合法状态

- 阶段：`0` 至 `6`。
- 门禁：`0` 至 `4`。
- 门禁状态：`pending`、`approved`、`rejected`、`superseded`。
- 任务状态：`not_started`、`in_progress`、`blocked`、`ready_for_review`、`complete`。

批准记录必须包含批准范围，不能只写“用户已通过”。
