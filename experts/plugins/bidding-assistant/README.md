# 招投标专家团（Bidding Assistant Team）

> WorkBuddy 专家包 · expertType: **team** · v1.0.0
>
> 面向投标人、招标人和评标支持人员，覆盖招标解析、投标编制、提交前合规审查、标书查重与围串标风险识别、评标报告生成的招投标全流程智能调度团队。

## 专家类型

**Team 型（专家团）**：1 名主理人 + 5 名专业成员。用户始终只与主理人对话，主理人按 **L0-L3 分层路由**调度成员——简单问题零调度，单项专业任务单次调度，正式/高风险任务才进入独立审查与全流程。

## 团队成员

| 角色 | Agent ID | 花名 | 职业头衔 | 绑定技能 |
|------|----------|------|----------|----------|
| 主理人 | bidding-assistant-team-lead | 钟招衡 | 首席招投标调度官 | —（只调度不执行） |
| 成员 | subagent-tender-analysis | 楚析真 | 招标文件分析员 | tender-document-analysis-and-bidding-assistant, word-document-processing |
| 成员 | subagent-bid-drafting | 裴编衡 | 投标文件编制员 | bid-document-generation, word-document-processing |
| 成员 | subagent-bid-compliance | 闵审慎 | 投标合规审查员 | tender-document-compliance-check, word-document-processing |
| 成员 | subagent-bid-integrity | 甄查鉴 | 标书一致性分析员 | bid-document-deduplication, word-document-processing |
| 成员 | subagent-bid-evaluation | 段评衡 | 评标分析员 | bid-evaluation-report-generation, word-document-processing |

## L0-L3 分层路由

| 级别 | 适用情形 | 子 Agent 调用 |
|---|---|---:|
| L0 即时沟通 | 能力说明、材料清单、流程解释、路由澄清、既有成果解读 | 0 |
| L1 单项快速 | 单独解析、单份编制、单次审查、单份查重、已有 manifest 的评标 | 1 |
| L2 标准协作 | 正式投标编制（解析→编制→合规审查）、提交前联合检查（合规+查重并行） | 2-3 |
| L3 全流程/高风险 | 完整投标项目、否决条款密集、候选终稿、两轮整改、多投标人综合评标 | 5-7 |

8 条工作流：`bidding_direct_dialogue` / `tender_analysis` / `bid_drafting_process` / `bid_compliance_review` / `bid_integrity_review` / `pre_submission_joint_check` / `bid_evaluation` / `bid_repair_cycle`。每条工作流有独立的必需技能证据、必需制品与核验要求（按工作流门禁，非全局一刀切）。

## 技能清单（6 项，复制自技能市场）

| 来源分类 | 技能 |
|---------|------|
| 常用工具·招投标（5） | tender-document-analysis-and-bidding-assistant, bid-document-generation, tender-document-compliance-check, bid-document-deduplication, bid-evaluation-report-generation |
| 常用工具·办公（1） | word-document-processing |
| 常用工具·招投标·共享模块 | _shared（deviation_atomic、bid_workspace、references，供技能脚本 import，不在 skills 数组声明） |

## 目录结构

```
bidding-assistant/
├── .codebuddy-plugin/
│   └── plugin.json          # 专家团配置（teamInfo + members + 6 skills）
├── avatars/                 # 头像（团队 + 主理人 + 5 成员）
│   ├── team.png                    # 团队头像
│   ├── bidding-assistant-team-lead.png  # 主理人头像
│   ├── subagent-tender-analysis.png
│   ├── subagent-bid-drafting.png
│   ├── subagent-bid-compliance.png
│   ├── subagent-bid-integrity.png
│   └── subagent-bid-evaluation.png
├── agents/
│   ├── bidding-assistant-team-lead.md   # 主理人（L0-L3 路由 + 工作流门禁）
│   ├── subagent-tender-analysis.md       # 招标文件分析员
│   ├── subagent-bid-drafting.md          # 投标文件编制员
│   ├── subagent-bid-compliance.md        # 投标合规审查员
│   ├── subagent-bid-integrity.md         # 标书一致性分析员
│   └── subagent-bid-evaluation.md        # 评标分析员
├── skills/                  # 6 项绑定技能（自技能市场复制）
│   ├── tender-document-analysis-and-bidding-assistant/
│   ├── bid-document-generation/
│   ├── tender-document-compliance-check/
│   ├── bid-document-deduplication/
│   ├── bid-evaluation-report-generation/
│   ├── word-document-processing/
│   └── _shared/
├── settings.json
└── README.md
```

## 主要工作流

### 单项直达

用户明确要求某一专项任务时，只调用对应子代理，不自动启动完整团队。

### 投标人全流程

```text
招标文件解析
→ 模板分流（官方 DOCX / PDF 重建待确认）
→ 已绑定文档能力处理模板并形成投标文件
→ 独立合规审查
→ 内容/版面/人工定点整改
→ 已绑定文档能力生成递增新版本
→ 全量复验（最多两轮）
→ 可选标书查重
```

### 提交前联合检查

```text
投标合规审查 ─┐
               ├→ 主 Agent 汇总提交阻断项和整改顺序
标书查重分析 ─┘
```

两项检查必须针对同一版本投标文件。

### 评标支持

```text
评标规则与投标人数据检查
→ 按需汇聚合规和查重结果
→ 否决条件处理
→ 分项评分和排名
→ 评标报告及看板
```

缺少评标方法或关键参数时阻断评分和排名。

## 核心交付门禁

- 招标解析阶段须生成结构化招标分析。
- 偏离表存在泛化、合并或关键要素缺失时，投标编制不得交付终稿。
- 编制阶段必须形成十五项质量清单；审查阶段必须形成十五项审查结果和定点整改计划。
- BQ 失败项必须记录物理 PDF 页和显示页码、章节、锚点、怎么改和如何复验。
- 候选终稿不得残留占位；整改不得覆盖原文件，自动整改最多两轮。
- 编制员自检不能替代合规审查员的独立提交前审查。
- 查重和围串标分析只形成风险线索，不直接认定违法事实。
- 评标报告不得补造评分参数，不替代评标委员会最终决定。

## 入职引导

| 字段 | 必填 | 用途 |
|---|---:|---|
| 使用角色 | 是 | 区分投标人、招标人和评标支持口径 |
| 默认工作口径 | 是 | 确定严格风控、平衡或效率优先 |
| 常用行业 | 否 | 优化项目背景和术语口径 |
| 交付偏好 | 否 | 选择 Word、HTML 或组合成果 |

## 设计要点（对照《开发方案总结》）

1. **架构保留 Agent Team**：五个子代理与五个专业 Skill 一一对应，职责分离合理。
2. **用户体验采用单 Agent**：用户始终只和主理人对话；简单沟通 0 次调度，单项专业任务 1 次调度，正式任务才组队。
3. **交付政策按工作流拆分**：L0 无制品要求、L1 结论+自检、L2/L3 才要求独立审查。
4. **能力闭环修复**：每个子代理绑定专项 Skill + word-document-processing，不依赖未绑定能力。
5. **有界恢复**：自动整改最多两轮，第二轮仍未关闭即转人工。

## 边界与转交

- 签署、递交、保证金、密封和截止时点等动作由有权人员确认。
- 不伪造资质/报价/签章，不代替递交或评标决定。
- 不直接认定串标，只形成风险线索。

## 数据与责任边界

Agent 包只保存配置和提示词，不包含真实招投标项目数据。资质、业绩、人员、报价、授权、签章、评分和候选人数据必须来自用户授权材料。系统输出用于工作辅助，最终投标、签章、递交、废标判断和评标决定由具有相应权限的人员确认。
