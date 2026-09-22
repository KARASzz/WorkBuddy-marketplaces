---
name: venture-blueprint-orchestration
description: Use when the Cece venture blueprint team starts a job, hands off between phases, or assembles the final business plan. Enforces task brief slots, source tags, and 8-part deliverable.
---

# 策策编排契约

## 何时使用

主理人 Phase 0 必读；每阶段交接必读；Phase 6 汇编必读。

## 使用前读取

- `templates/task-brief.md`
- `templates/handoff.md`
- `templates/business-plan.md`
- `templates/source-tags.md`

## 铁律

1. 先填《任务简报》再 spawn。
2. 交接必须带：上游完整原文 + 本阶段要回答的问题清单 + 禁止越权清单。
3. 事实句必须带来源标签，见 `templates/source-tags.md`。
4. 最终交付必须覆盖 `templates/business-plan.md` 的 8 节，缺节写「未完成 + 原因」。
5. 法定资质、对外承诺、资金决策、数据合规不得由模型终裁，进「待人工确认」。

## 阶段产出指针

| Phase | Agent ID | 模板 |
|-------|----------|------|
| 0 | venture-blueprint-team-lead | task-brief.md |
| 1 / 1b | track-scanner | 成员 MD 输出规范；Workflow B 用轻量子集 |
| 2 | business-architect | 成员 MD 方案卡 |
| 3 | unit-economics-analyst | 成员 MD 五节测算 |
| 4 | landing-simulator | 成员 MD 六节推演 |
| 5 | risk-audit-officer | 成员 MD 六节审计 |
| 6 | venture-blueprint-team-lead | business-plan.md |
