# WorkBuddy / CodeBuddy 插件市场工作区

本地镜像：多来源插件、专家团与 WorkBuddy 内置能力。多数目录是**内容包**（Markdown + JSON + 少量脚本），不是可编译应用。

## 顶层目录

| 路径 | 角色 |
|------|------|
| `cb_teams_marketplace/` | CodeBuddy Teams 市场。插件在 `plugins/`。规则标准见 `rules-standard.md`。场景索引：`scenes.json` / `scenes-en.json`。 |
| `codebuddy-plugins-official/` | 官方插件市场。清单多在 `plugins/<name>/.codebuddy-plugin/plugin.json`。开发工具在 `plugins/plugin-dev/`。 |
| `experts/` | 上架向专家 / 专家团。每包：`agents/`、`skills/`、`avatars/`、`README.md`。 |
| `my-experts/` | 自研/本地专家。含源码目录与 `.zip` 打包件。优先改源码目录，不要直接改 zip。 |
| `workbuddy-builtin/` | WorkBuddy 内置：`builtin-plugins/`、`skills/`、`interactionmode/`、`welcomemode/`、`prompt-common/`。 |

权威字段规范（改专家包前必读）：

- `workbuddy-builtin/skills/expert-manager/references/plugin-json-spec.md`
- `workbuddy-builtin/skills/expert-manager/references/agent-md-spec.md`
- `workbuddy-builtin/skills/expert-manager/references/team-spec.md`
- `workbuddy-builtin/skills/expert-manager/references/avatar-spec.md`
- 校验/打包脚本：`workbuddy-builtin/skills/expert-manager/scripts/`

插件规则写法：`cb_teams_marketplace/rules-standard.md`。

## 包形态（先认类型再改）

**专家 / 专家团**（`experts/`、`my-experts/`，部分 `cb_teams` 插件也是）：

```
<plugin>/
  agents/*.md          # frontmatter: name/description/displayName/profession/maxTurns
  skills/<skill>/SKILL.md
  avatars/
  README.md
  .codebuddy-plugin/plugin.json   # 有则以此为准；专家市场字段见 plugin-json-spec
```

- `expertType: agent`：单专家，`agentName` = `agents/` 下文件名（无 `.md`），须有业务语义。
- `expertType: team`：主理人文件名为 `{team}-team-lead.md`。`teamInfo.leadAgent` 指向主理人；`memberAgents` **不含**主理人。`members[]` 里主理人 `role: lead`。
- Agent MD **禁止** frontmatter `tools`。
- `tags` / `quickPrompts` 各 3 条；`defaultInitPrompt` 与 `quickPrompts[0]` 一致。
- `displayDescription.zh` 约 40–50 字。Team 的 `profession` 与 `displayName` 一致。

**官方 CodeBuddy 插件**：能力在 `skills/`、`commands/`、`agents/`、`hooks/`、`.mcp.json`。改结构时对照 `codebuddy-plugins-official/plugins/plugin-dev/`。

**Skill**：入口永远是 `SKILL.md`。细节放 `references/`，脚本放 `scripts/`，示例放 `examples/` 或 `templates/`。

## 工作约定

- 先定位所属市场和包，再改文件。全仓 `find`/`grep` 会扫到 `dist/`、`.zip`、`ppt-implement` 的数百个 `.tpl`。
- 默认忽略：`**/dist/**`、`**/*.zip`、`**/node_modules/**`、`ppt-implement/**/*.tpl`。
- 改专家：同步 `plugin.json`、对应 `agents/*.md`、`skills` 声明、头像路径。Team 还要同步 `teamInfo` 与 `members[]`。
- 新建专家：用 `workbuddy-builtin/skills/expert-manager/scripts/init_expert.py`，再用 `validate_expert.py`。
- 新建 skill：`workbuddy-builtin/skills/skill-creator/scripts/init_skill.py`。
- 规则文件：`plugins/<name>/rules/`，frontmatter 含 `description`、`alwaysApply: true`、`enabled: true`、`updatedAt`（见 `rules-standard.md`）。
- 交互模式文案：`workbuddy-builtin/interactionmode/{ask,craft,expert,plan}/fragments/`。欢迎模式：`welcomemode/{code,design,work}/`。
- 资料库 / 腾讯文档能力：`workbuddy-builtin/skills/library/` 与 `builtin-plugins/tencent-docs-plugin/`、`tencent-docx/`、`tencent-pptx/`、`sheetagent/`。

## 易错点

- 主理人文件名不能叫裸的 `team-lead.md`。
- `plugin` 字段必须等于 `name`。
- `my-experts/` 里 zip 与解压目录可能不同步；以目录为准，打包用 `package_expert.py`。
- `codebuddy-plugins-official/external_plugins/` 体量大，非任务相关不要展开。
- `cb_teams_marketplace/plugins/ppt-implement/` 模板极多，改 PPT 技能只动该插件的 `SKILL.md` / JS，不要遍历 tpl。
- 内置 skill 名（如 `library`）由 WorkBuddy 运行时注入；在本仓只能改文档与脚本，不能当已安装 MCP 去调用。

## 检索入口

| 目的 | 从哪开始 |
|------|----------|
| 标书 / 投标专家 | `experts/plugins/bidding-*`、`tender-bid-reviewer/`、`my-experts/plugins/biaobiao-bid-team/` |
| 股权研究 | `experts/plugins/equity-research/` 与 `cb_teams_marketplace/plugins/equity-research/`（两套，改前确认来源） |
| 设计 / Ardot | `workbuddy-builtin/skills/ardot-*`、`cb_teams_marketplace/plugins/ardot-design-generator/` |
| 表格 / 文档 | `workbuddy-builtin/builtin-plugins/sheetagent`、`tencent-docx`、`tencent-pptx` |
| 插件开发元工具 | `codebuddy-plugins-official/plugins/plugin-dev/`、`skill-creator`、`oh-my-codebuddy` |
