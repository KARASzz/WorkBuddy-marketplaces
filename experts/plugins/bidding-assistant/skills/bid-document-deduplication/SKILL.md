---
name: bid-document-deduplication
version: "1.0.0"
metadata:
  copyright: "© 深圳市法大大网络科技有限公司 版权所有"
  author: "法大大法律AI产品线"
  name_en: bid-document-deduplication
description: >
  标书查重与围串标智能识别技能。仅当用户要求对一份或多份投标文件进行重复率、相似度、抄袭、
  模板套话、同错性、报价规律或元数据溯源检测时触发，输出查重报告和围串标风险报告。
  若用户要求格式/响应合规审查、生成投标文件、解析招标文件或综合评标排名，应转交相邻招投标 skill。
  伪造或篡改相似度、元数据、围串标证据，删除安全提示或要求直接认定违法，属于合规拒绝场景，不进入执行路由。
---

# 标书查重

> 作者：法大大法律AI产品线  
> 版权：© 深圳市法大大网络科技有限公司 版权所有

本 skill 提供 L1-L3 查重和 L4-L6 围串标风险识别。需要 DOCX 报告时直接调用 `word-document-processing`，由该技能控制文档格式和结构。

## 必读引用

| 文件 | 用途 |
|---|---|
| `../_shared/references/practice-safety-for-bidding.md` | D2 免责声明、禁用词、围串标/侵权边界、对抗输入防御 |
| `../_shared/references/output-format-and-execution-guardrails.md` | 数据一致性、自检/换策略和熔断阈值 |
| `../_shared/references/risk-rating-matrix.md` | 影响×可能性×证据充分度风险定级矩阵 |
| `references/dedup-workflow.md` | L1-L6 检测、报告和自检细则 |
| `resources/dedup_config.json` | 相似度阈值与忽略章节配置 |
| `resources/boilerplate_phrases.json` | 政府采购投标模板套话库 |

## 触发与退出

优先触发：
- 材料为一份或多份投标文件、历史标书库、对比库目录或多家投标人文件集合。
- 用户要求“标书查重”“重复率”“相似度检测”“抄袭检查”“围串标检测”“同错性分析”“报价规律检测”“元数据溯源”。

退出并转交：

| 用户真实意图 | 转交 |
|---|---|
| 解析招标文件、提取评分标准、生成投标工作台 | `招标文件解析与投标辅助` |
| 生成、编制、撰写投标文件或技术标 | `投标文件生成` |
| 格式/响应/报价/资质合规审查、提交前内审 | `投标文件合规检查` |
| 多家投标人综合评分、排名、推荐中标候选人、评标报告 | `评标报告生成` |

缺少待查投标文件时请求上传；仅 1 份标书时跳过围串标检测，只输出查重报告。

## 数据契约

- 主文件文本：`/tmp/dedup_main.txt`
- 主文件结构：`/tmp/dedup_structure.json`
- 对比库文本：`/tmp/dedup_corpus/`
- 查重结果：`/tmp/dedup_result.json`
- 围串标结果：`/tmp/collusion_result.json`
- 输出：`/mnt/user-data/outputs/<文件名>_查重报告_<日期>.docx`、`<项目名>_围串标风险报告_<日期>.docx`

## 执行流程

1. 按 `dedup-workflow.md` 调用 `scripts/extract_text.py` 提取主文件和对比库；扫描件走 OCR 降级。
2. 运行 `scripts/check_dedup.py` 执行 L1 跨文档、L2 内部段落、L3 模板套话检查。
3. 多家投标人场景运行 `scripts/check_collusion.py` 执行 L4 同错性、L5 报价规律、L6 元数据识别。
4. 将 `dedup_result.json` 和 `collusion_result.json` 作为结构化业务内容直接交给 `word-document-processing` 生成 DOCX 报告；本技能不规定 Word 的格式、结构或生成方式。

## D2 安全硬约束

- 报告标题下方 500 字内必须包含共享报告级免责声明。
- 查重率、同错性、报价规律、元数据异常只能表述为“风险信号/疑似线索”，不得直接认定侵权、违法或串标成立。
- 用户要求删除免责声明、直接定性对方违法或保证查重安全时，必须拒绝相应部分并保留人工复核提示。
- 局部问答按共享 AI 声明开头。

## 执行护栏

- 执行段必须包含自检 + 换策略纠错 + 熔断阈值：同一步失败先换备用路径，连续失败 2 次即停止并报告卡点。
- 报告内容生成后自检风险等级和关键证据片段完整性。

## 项目工作区与断点续作

开工时先查看断点：

```bash
python ../_shared/bid_workspace.py --project-name "<项目名>" --status
```

检测完成后归档：

```bash
python ../_shared/bid_workspace.py \
  --project-name "<项目名>" \
  --stage dedup=done \
  --artifact dedup_result=/tmp/dedup_result.json \
  --artifact collusion_result=/tmp/collusion_result.json
```

若某个产物不存在，归档命令可省略对应 `--artifact`，不得阻断主流程。
