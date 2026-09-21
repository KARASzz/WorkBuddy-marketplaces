# 标标 · 标书制作专家（Bid Writing Expert）

海宁亚大塑料管道系统有限公司的专职标书制作专家：解析招标文件、复用历史标书资产库，分阶段产出投标文件（每阶段人工审核），并通过投标结果复盘持续升级制作质量。

## 类型

Agent 型（单个 AI 专家）

## 功能

- **招标文件深度解析**：提取资质门槛、技术要求、评分办法、废标条款、关键时间节点，输出《招标解析报告》
- **历史资产复用**：在历史标书库中匹配可复用的资质、业绩、技术方案素材，标注"可复用/需改写/需新写/缺失待补"
- **分阶段标书制作**：解析 → 策略 → 分册制作（商务册/技术册/价格册）→ 整合校对 → 定稿归档，每阶段设人工审核门禁
- **投标复盘迭代**：录入投标结果字段，生成复盘报告，沉淀经验并升级素材库与应答策略

## 配套资源

- `skills/bid-writing/references/bid-structure.md` — 投标文件标准结构（商务/技术/价格册）
- `skills/bid-writing/references/retrospective-fields.md` — 投标结果字段规范
- `skills/bid-writing/templates/bid-analysis-report.md` — 招标解析报告模板
- `skills/bid-writing/templates/retrospective-report.md` — 投标复盘报告模板

## 使用示例

- 我收到了一份新招标文件，帮我启动投标文件的分阶段制作流程
- 从历史标书库中匹配本项目可复用的资质、业绩和技术方案素材
- 本次投标结果已出，帮我录入结果字段并生成复盘报告

## 头像

头像已自动生成在 `avatars/` 目录下。如需替换为自定义头像，要求：
- 格式：PNG（推荐）或 JPG
- 尺寸：512×512 px
- 大小：单张不超过 500KB

## 安装

将专家包目录放到专家目录下：

```
/Users/karas/.workbuddy/plugins/marketplaces/my-experts/plugins/bid-writing-expert/
```

然后运行注册命令使其可见：

```bash
python3 scripts/register_expert.py <expert-dir>
```

## 打包分享

```bash
python3 scripts/package_expert.py <expert-dir> [output-dir]
```
