# 策策商业策划团（Cece Venture Blueprint）

面向新兴细分赛道的商业模式探索团队：把一个陌生的行业方向拆解成可判断的赛道，设计可落地的商业模式，算清单位经济，推演实施路径，并在执行前完成风险与 AI 治理审计，最终输出一份可落地、可审计、可止损的商业策划案。

## 类型

Team 型（多角色协作团队）：1 名主理人 + 5 名专业成员，按 SOP 分阶段串并行协作。编排契约见 `skills/venture-blueprint-orchestration/`。

## 团队成员

| 成员 ID | 名字 | 职业头衔 | 职责 |
|---|---|---|---|
| venture-blueprint-team-lead | 沈立策 | 商业操盘总策划 | 任务定义、编排调度、冲突裁决、汇编交付 |
| track-scanner | 温识新 | 新兴赛道研究员 | 赛道切分、需求与供给信号、价值窗口与时机判断、机会点收敛 |
| business-architect | 谷知商 | 商业模式架构师 | 多套商业模式方案设计、收入模型、壁垒假设、方案比选 |
| unit-economics-analyst | 钟衡之 | 单位经济测算师 | 基准参数、单位经济与财务测算、盈亏平衡、敏感性分析 |
| landing-simulator | 程可达 | 落地推演官 | MVP、里程碑与门禁、资源与前置条件、失败模式与止损线 |
| risk-audit-officer | 曾无虞 | 风险与AI治理审计官 | 风险登记与预案、AI 使用安全与合规审计、红线与人工确认点 |

## 工作框架

| 阶段 | 内容 | 执行方式 |
|---|---|---|
| Phase 0 | 任务定义：7 槽任务简报 | 主理人 |
| Phase 1 | 赛道基线：赛道地图 + 行业基准参数库 | track-scanner ∥ unit-economics-analyst |
| Phase 1b | 轻量信号校验（Workflow B 固定步骤） | track-scanner |
| Phase 2 | 模式设计：3 套候选方案 + 推荐与假设清单 | business-architect |
| Phase 3 | 经济性测算：单位经济、现金流、敏感性与翻转点 | unit-economics-analyst |
| Phase 4 | 落地推演：MVP、里程碑门禁、前置条件、止损线 | landing-simulator |
| Phase 5 | 风险与 AI 治理审计：风险登记、审计清单、红线、总体裁定 | risk-audit-officer |
| Phase 6 | 汇编交付：《商业策划案》8 部分标准交付物 | 主理人 |

## 输出物标准

最终《商业策划案》必须包含：结论摘要、赛道判断、推荐商业模式、经济性结论、落地路线、风险与预案、待验证假设清单、待人工确认事项。模板：`skills/venture-blueprint-orchestration/templates/business-plan.md`。

每条事实性结论标注来源类型：`[实测]` / `[可比]` / `[推算]` / `[假设]`。

## 使用示例

- 帮我拆解一个新兴细分赛道：判断价值窗口与进入时机，并给出可落地的商业模式假设
- 基于我的资源与能力清单，设计商业模式与单位经济模型，并给出 90 天最小验证路径
- 对我现有的商业策划案做落地推演与风险审计，重点检查 AI 使用安全、数据合规与失败预案
- 只做风险部分：这套 AI 辅助交付流程的数据来源和留痕怎么设计才可审计？

## 头像

头像位于 `avatars/` 目录。如需替换为自定义头像，要求：
- 格式：PNG（推荐）或 JPG
- 尺寸：512×512 px
- 大小：单张不超过 500KB

## 安装前校验

```bash
python3 ~/.workbuddy/plugins/marketplaces/workbuddy-builtin/skills/expert-manager/scripts/validate_expert.py \
  ~/.workbuddy/plugins/marketplaces/my-experts/plugins/venture-blueprint-team
```

期望输出：`✅ Expert package is valid!`

Team 根目录须有 `settings.json`，且 `"agent"` 等于 `venture-blueprint-team-lead`。

## 安装

将专家包目录放到专家目录下：

```
~/.workbuddy/plugins/marketplaces/my-experts/plugins/venture-blueprint-team/
```

然后运行注册命令使其可见（会写入 marketplace.json）：

```bash
python3 ~/.workbuddy/plugins/marketplaces/workbuddy-builtin/skills/expert-manager/scripts/register_expert.py \
  ~/.workbuddy/plugins/marketplaces/my-experts/plugins/venture-blueprint-team
```

## 打包分享

```bash
python3 ~/.workbuddy/plugins/marketplaces/workbuddy-builtin/skills/expert-manager/scripts/package_expert.py \
  ~/.workbuddy/plugins/marketplaces/my-experts/plugins/venture-blueprint-team
```
