# 策策专家团升级方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `venture-blueprint-team` 通过 WorkBuddy 校验并可注册，同时收紧 SOP 歧义、抽出交付模板、降低主理人 prompt 里的身份过拟合。

**Architecture:** 不改角色数量与 Agent ID（禁止改 `name` / 文件名）。P0 补齐安装契约；P1 改主理人 SOP 与成员轮次；P2 新增一个编排 Skill + 模板，Agent MD 改为引用模板；P3 展示文案与 README。不做新成员、不做新专家类型。

**Tech Stack:** WorkBuddy 专家包（`plugin.json` + Agent MD + Skill MD），校验命令 `python3 workbuddy-builtin/skills/expert-manager/scripts/validate_expert.py`。

**包根目录：** `my-experts/plugins/venture-blueprint-team/`

---

## 文件地图

| 路径 | 动作 |
|------|------|
| `settings.json` | 新建。Team 硬性契约。 |
| `.codebuddy-plugin/plugin.json` | 改展示名、英文成员姓氏、`displayDescription`、可选 `skills`。 |
| `agents/venture-blueprint-team-lead.md` | 改服务对象、Workflow B、Skill 引用、工具映射说明。 |
| `agents/track-scanner.md` 等 5 个成员 | `maxTurns`、输出节改为指向模板。 |
| `skills/venture-blueprint-orchestration/SKILL.md` | 新建。阶段契约、交接、来源标签。 |
| `skills/venture-blueprint-orchestration/templates/*.md` | 新建。任务简报、策划案、交接单。 |
| `README.md` | 同步展示名、settings、skill。 |

不改：`agents/` 文件名、`plugin.json.name`、`agentName`、`teamInfo.memberAgents` ID、头像文件名（除非重新生成，本方案不强制）。

---

## 原则（升级时不要破）

- Agent ID 保持：`venture-blueprint-team-lead` / `track-scanner` / `business-architect` / `unit-economics-analyst` / `landing-simulator` / `risk-audit-officer`。
- Team：`profession` 必须等于 `displayName`（中英文各自相等）。
- `tags` / `quickPrompts` 仍各 3 条；`defaultInitPrompt` = `quickPrompts[0]`。
- 主理人不代写专业结论；成员必须 SendMessage 回传完整原文。
- `displayDescription.zh` 控制在 40–50 字。

---

### Task 1: 补 Team 安装契约

**Files:**
- Create: `my-experts/plugins/venture-blueprint-team/settings.json`

- [ ] **Step 1: 写入 settings.json**

```json
{
  "agent": "venture-blueprint-team-lead"
}
```

- [ ] **Step 2: 跑校验**

```bash
python3 workbuddy-builtin/skills/expert-manager/scripts/validate_expert.py my-experts/plugins/venture-blueprint-team
```

Expected: 不再出现 `Team type must have settings.json`。允许仍有 warning，不允许新的 error。

---

### Task 2: 展示名与成员英文名

**问题：** 卡片上只看到「策策」，看不出业务；英文名用了全拼（`Shen Lice`），规范要求拼音姓。

**Files:**
- Modify: `my-experts/plugins/venture-blueprint-team/.codebuddy-plugin/plugin.json`

- [ ] **Step 1: 改团队展示字段**

```json
"displayName": {
  "en": "Cece Venture Blueprint",
  "zh": "策策商业策划团"
},
"profession": {
  "en": "Cece Venture Blueprint",
  "zh": "策策商业策划团"
},
"displayDescription": {
  "en": "Deconstruct emerging niche tracks, design landable models, and stress-test unit economics, rollout paths and AI-governance risk.",
  "zh": "拆解新兴细分赛道，设计可落地商业模式，完成单位经济、落地推演与AI治理审计。"
}
```

中文描述字数须在 40–50（含标点）。上句 42 字量级，改完用 `len()` 数一遍。

- [ ] **Step 2: members[].displayName.en 改为拼音姓**

| id | 现 en | 改后 en |
|----|-------|---------|
| venture-blueprint-team-lead | Shen Lice | Shen |
| track-scanner | Wen Shixin | Wen |
| business-architect | Gu Zhishang | Gu |
| unit-economics-analyst | Zhong Hengzhi | Zhong |
| landing-simulator | Cheng Keda | Cheng |
| risk-audit-officer | Zeng Wuyu | Zeng |

中文花名不变。

- [ ] **Step 3: 同步各 Agent MD frontmatter 的 `displayName.en`**，与 plugin.json 一致。`profession` 成员级保持现有职业头衔（主理人仍是 Chief Venture Architect / 商业操盘总策划）。

---

### Task 3: 主理人 — 服务对象、Workflow B、工具映射

**Files:**
- Modify: `my-experts/plugins/venture-blueprint-team/agents/venture-blueprint-team-lead.md`

- [ ] **Step 1: 替换过拟合履历段**

删除「独立开发者 / 开源项目维护者 / … 执行主任」 enumeration。改为：

```markdown
你的服务对象是要把陌生新兴赛道做成可决策方案的操盘者。默认同时给出两条路径的可行性差异：
1. **小团队冷启动**：少人、低资质门槛、短验证周期。
2. **产业侧资源对接**：可借用渠道、算力、园区或客户关系，但前置条件更重。

具体身份、预算、资质从《任务简报》读取，禁止把未声明的身份写进结论。
```

- [ ] **Step 2: 写死 Workflow B（取消「可选」）**

```markdown
### Workflow B：模式快诊与测算
- **触发条件**：用户已明确赛道边界与初步生意想法，主要要模式、测算与风险。
- **Phase 编排（固定，不可再标可选）**：
  1. Phase 0（轻）
  2. Phase 1b：`track-scanner` **轻量信号校验**（只做：细分是否成立、付费信号有无、时机偏早/合适/偏晚；不做完整赛道地图）
  3. Phase 2：`business-architect`
  4. Phase 3：`unit-economics-analyst`
  5. Phase 5：`risk-audit-officer`
  6. Phase 6：汇编
- **跳过条件（唯一例外）**：用户已提交成文的赛道结论（含细分定义 + 至少 3 条带来源的信号），则跳过 Phase 1b，并在任务简报标注「赛道结论为用户给定」。
```

- [ ] **Step 3: 在协作规则后增加运行时工具映射**（不删 TeamCreate 铁律原文，以免 WorkBuddy 运行时丢协议）

```markdown
## 运行时工具映射

按宿主实际工具执行铁律，语义不变：

| 铁律动作 | WorkBuddy | Grok / 本仓会话 |
|----------|-----------|-----------------|
| 建立团队 | TeamCreate | 在首条调度前向用户声明团队成员清单与边界（等价建团） |
| 调度成员 | Agent(name=成员ID, subagent_type=成员ID) | spawn_subagent，prompt 内写明 Agent ID 与回传格式 |
| 成员回传 | SendMessage → 主理人 | 子代理最终消息必须含完整产出原文；主理人等待回收后再进入下一 Phase |

禁止用中文名或自创 ID spawn。禁止主理人模拟成员口吻一次性写完全团产出。
```

- [ ] **Step 4: Phase 0 增加《任务简报》必填槽**

```markdown
《任务简报》固定 7 槽，缺槽标 `[假设]` 或 `[待用户确认]`：
赛道陈述 / 操盘主体 / 资源约束 / 路径偏好（冷启动|产业对接|双路径） / 期望输出 / 成功判据 / 止损底线
```

- [ ] **Step 5: 主理人 frontmatter 增加 skills 预加载**

```yaml
skills: [venture-blueprint-orchestration]
```

---

### Task 4: 成员 maxTurns 与职责边界微修

**Files:**
- Modify: `agents/track-scanner.md`（maxTurns 60 → 100）
- Modify: `agents/risk-audit-officer.md`（60 → 80）
- Modify: `agents/business-architect.md`、`unit-economics-analyst.md`、`landing-simulator.md`（保持 60，或统一 80）

- [ ] **Step 1: 仅上调需要检索/审计的角色**

```yaml
# track-scanner.md
maxTurns: 100

# risk-audit-officer.md
maxTurns: 80
```

测算 / 模式 / 落地以结构化表格为主，60 足够；不要无故加轮次。

- [ ] **Step 2: track-scanner 注意事项增加一句**

```markdown
轻量模式（Workflow B 的 Phase 1b）：只输出「价值窗口判断 + 信号证据表（≤8 行）+ 未查清项」，禁止展开完整六节赛道地图。
```

---

### Task 5: 抽出编排 Skill 与模板

**目的：** Agent MD 变瘦；交接格式唯一。只建 **一个** skill，不按成员拆五个。

**Files:**
- Create: `skills/venture-blueprint-orchestration/SKILL.md`
- Create: `templates/task-brief.md`
- Create: `templates/handoff.md`
- Create: `templates/business-plan.md`
- Create: `templates/source-tags.md`
- Modify: `plugin.json` 增加 `"skills": ["./skills/venture-blueprint-orchestration"]`

- [ ] **Step 1: SKILL.md 核心约定（写入文件，不要只写在对话里）**

```markdown
---
name: venture-blueprint-orchestration
description: Use when the Cece venture blueprint team starts a job, hands off between phases, or assembles the final business plan. Enforces task brief slots, source tags, and 8-part deliverable.
---

# 策策编排契约

## 何时使用
主理人 Phase 0 必读；每阶段交接必读；Phase 6 汇编必读。

## 铁律
1. 先填《任务简报》再 spawn。
2. 交接必须带：上游完整原文 + 本阶段要回答的问题清单 + 禁止越权清单。
3. 事实句必须带来源标签，见 templates/source-tags.md。
4. 最终交付必须覆盖 templates/business-plan.md 的 8 节，缺节写「未完成 + 原因」。
5. 法定资质、对外承诺、资金决策、数据合规不得由模型终裁，进「待人工确认」。

## 阶段产出指针
| Phase | Agent ID | 模板 |
|-------|----------|------|
| 0 | 主理人 | task-brief.md |
| 1 / 1b | track-scanner | 成员 MD 输出规范；B 用轻量子集 |
| 2 | business-architect | 成员 MD 方案卡 |
| 3 | unit-economics-analyst | 成员 MD 五节测算 |
| 4 | landing-simulator | 成员 MD 六节推演 |
| 5 | risk-audit-officer | 成员 MD 六节审计 |
| 6 | 主理人 | business-plan.md |
```

- [ ] **Step 2: task-brief.md** 七槽空表（赛道 / 主体 / 约束 / 路径偏好 / 输出 / 成功判据 / 止损）。

- [ ] **Step 3: handoff.md**

```markdown
# 阶段交接单
- 上游 Agent ID：
- 下游 Agent ID：
- 本阶段问题（3–7 条，必须回答）：
- 禁止越权：
- 上游原文：（整段粘贴，禁止摘要代替）
```

- [ ] **Step 4: business-plan.md** 复制主理人「输出物标准」8 节为填空模板。

- [ ] **Step 5: source-tags.md** 四标签定义 + 反例（无来源的市场规模数字）。

- [ ] **Step 6: plugin.json 声明 skills**

```json
"skills": ["./skills/venture-blueprint-orchestration"]
```

- [ ] **Step 7: 五个成员 MD 的「输出规范」开头加一行**

```markdown
完整表格结构以团队 skill `venture-blueprint-orchestration` 与主理人交接单为准；本节为该角色的必填节。
```

不要把整份模板再复制进每个成员 MD。

---

### Task 6: README 与校验注册

**Files:**
- Modify: `my-experts/plugins/venture-blueprint-team/README.md`

- [ ] **Step 1: 标题与成员表与 plugin.json 展示名对齐**（策策商业策划团）。

- [ ] **Step 2: 增加「安装前校验」**

```bash
python3 ~/.workbuddy/plugins/marketplaces/workbuddy-builtin/skills/expert-manager/scripts/validate_expert.py \
  ~/.workbuddy/plugins/marketplaces/my-experts/plugins/venture-blueprint-team
```

Expected: `✅ Expert package is valid!`

- [ ] **Step 3: 注册（仅当用户明确要求上架到专家中心）**

```bash
python3 workbuddy-builtin/skills/expert-manager/scripts/register_expert.py \
  my-experts/plugins/venture-blueprint-team \
  --session-id "${CODEBUDDY_SESSION_ID:-local}"
```

本方案默认做到校验通过即可；注册会写 `marketplace.json`，需用户点头再跑。

---

## 明确不做（本轮）

- 不新增第 6 名成员（如「政策研究员」）——赛道研究员已覆盖政策信号。
- 不重做头像（现有 `avatars/*.png` 可用；若以后重做，背景色用 `deep teal with silver accent`，category 12）。
- 不把测算做成 Python 模型——新兴赛道缺稳定数据，表格 + 来源标签更诚实。
- 不改专家目录名 / `plugin.json.name`。

---

## 验收清单

1. `validate_expert.py` 零 error。
2. Workflow B 文本中不再出现「可选」。
3. 主理人 MD 无具体职务履历枚举。
4. `plugin.json.skills` 指向的目录含 `SKILL.md`。
5. `settings.json.agent` == `agentName` == 主理人文件名。
6. 抽查：成员 MD 仍有 SendMessage 回传 `venture-blueprint-team-lead`。
7. `displayDescription.zh` 40–50 字；Team `profession` == `displayName`。

---

## 建议实施顺序

P0（10 分钟）：Task 1  
P1（30–40 分钟）：Task 2–4  
P2（40 分钟）：Task 5  
P3（10 分钟）：Task 6  

P0 单独可交付（专家能被检测到）。P1 修运行时行为。P2 修可维护性。
