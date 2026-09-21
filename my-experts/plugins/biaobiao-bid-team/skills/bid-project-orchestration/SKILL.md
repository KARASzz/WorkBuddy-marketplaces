---
name: bid-project-orchestration
description: Use when starting, resuming, routing, gating, versioning, or coordinating a Haining Yada bid project across multiple specialist members.
version: "2.1.0"
category: bidding
---

# 投标项目编排

## 使用前读取

- `references/team-operating-contract.md`
- `references/project-state-schema.md`
- 新项目使用 `templates/project-register.md`
- 请求人工批准时使用 `templates/gate-decision.md`
- 成员交接使用 `templates/member-handoff.md`

## 核心原则

标标维护一个事实版本、一个要求—响应—证据矩阵和一套门禁状态。成员可以并行工作，但不得各自创造项目真相。

## 启动

1. 判断完整项目或专项任务。
2. 确定项目目录、项目简称、招标文件与附件清单。
2.5 执行阶段 0.5 招标包完整性核验，形成《招标包完整性核验表》，等待门禁 #0。
3. 创建项目状态台账，所有门禁初始为 `pending`。
4. 记录来源版本；未实际读取的文件不得标为已处理。
5. 把首个任务委派给研标官。

## 续作

先读取最近的项目状态台账和已批准成果，核对源文件是否变化。无法证明当前台账是最新版本时，停止续写并列出需要核对的文件。

## 门禁控制

只有用户对明确成果范围作出批准才更新门禁。每次批准都写入独立记录，包含批准人、时间、文件、版本和保留意见。补遗、澄清、关键证据或报价变化会使受影响门禁变为 `superseded`。

## 并行规则

只有门禁 #2 通过后，商务与技术分册才可并行。独立终审必须在所有分册通过门禁 #3 后开始。最终 Word 只能在门禁 #4 通过后由 WorkBuddy 生成。

## 常见错误

- 把“继续做”当成人工批准。
- 成员使用不同招标版本。
- 只在对话中记录结论，不写 Markdown 文件。
- 新补遗出现后继续沿用旧批准。
- 为节省时间跳过独立终审。
- 招标包只收到部分册次就开始解析（双册制漏收技术册或商务册）。
- 迟到文件到手后沿用旧批准，未把受影响门禁标为 `superseded`。
- 把“能解析出内容”当作“资料已完整”，未做应有/实收对照。
