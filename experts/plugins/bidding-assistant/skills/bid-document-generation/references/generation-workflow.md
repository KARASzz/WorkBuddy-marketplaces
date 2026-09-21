# 投标文件生成工作流细则

## 1. 输入

- 首选 `/tmp/tender_analysis.json` 和 `/tmp/company_profile.json`。
- 无解析结果时，提示先运行“招标文件解析与投标辅助”或提供招标文件。
- 企业资料不足时，一次性列出缺口，不多轮零散追问。

## 2. 企业资料

使用 `scripts/load_company_profile.py --check --output /tmp/company_profile.json` 读取资料库；需要保存时使用 `--save /tmp/company_profile.json --store`。

不得编造资质、业绩、人员、证书编号、投标总价或授权信息。过程稿缺料统一使用 `【待补充|BQ06|事项|责任人|截止时间】`，同步写入质量台账；候选终稿不得保留任何未关闭占位。

## 3. 内容目录与正文

- `bid_outline.json` 每个节点保存招标原文 `source_heading`、`heading_level` 和来源位置，作为 Word 技能生成文档时的业务输入。
- 目录由 `tender_analysis.scoring.technical_score.items` 驱动，每个评分项至少有一个响应章节。
- 高权重项按 `technical-writing-patterns.md` 十节骨架展开，必须含“招标需求响应总述”和“服务承诺”。
- 正文按“定位/原因 → 机制/流程 → 量化承诺”成段论述；关键参数与招标原文一致。
- 关键章节 800-1500 字，辅助章节 300-600 字。

## 4. 商务十二件套

按 `business-doc-suite.md` 裁剪生成：投标函、授权委托书、报价表、商务响应偏离表、法人身份证明、承诺书、保证金、资格审查资料、财务状况、类似业绩、项目人员、其他加分材料。

缺少真实材料时写入独立缺料清单，不得编造或把占位内容当作正式信息。

生成商务文件前先生成原子化偏离表：

```bash
python scripts/build_deviation_tables.py \
  --requirements /tmp/tender_analysis.json \
  --responses /tmp/deviation_responses.json \
  --output /tmp/deviation_tables.json
```

`ok=false` 或存在 blocker 时停止。偏离表 JSON 直接交给 `word-document-processing` 生成文档表格。

## 5. 结构化内容与 DOCX 生成

- `navigation-tables.md` 生成资格审查、符合性审查和评标导航表的业务数据。
- 从 `tender_analysis.star_clauses` 生成“★条款响应对照表”业务数据。
- 将招标方提供的格式文件、`bid_outline.json`、章节正文、商务材料、偏离表、导航表、索引数据和用户指定图片目录直接交给 `word-document-processing`。
- DOCX 的模板选择、目录、标题、分页、表格、填空项、勾选项、图片插入、页眉页脚和页码回填均由 Word 技能自行控制；本技能不规定其内部生成方式、格式参数或排版校验流程。
- 企业资料可选提供 `material_files` 映射；匹配到的证照/证明图片会直接插入，非图片材料或缺失材料进入人工核查清单。

## 6. 业务自检重点

- 投标总价不得超过最高限价。
- 检查评分项覆盖率、★条款对照表、导航表、商务材料状态和响应索引数据。
- 检查项目名称、编号、主体、报价、税率、期限和关键参数在结构化业务数据中一致。
- 按 `bid-quality-preflight.md` 生成 `bid_quality_manifest.json`，覆盖 BQ01-BQ15；证据材料引用具体到材料名、图号和章节。
- 全量解析“见第X节、见图X-X、见表X-X、见附件X”等交叉引用，目标缺失或不唯一时阻断候选终稿。
- 建立关键承诺数字台账、日期台账、敏感信息台账和逐页签章目标清单；无真实依据时转人工。
- DOCX 的格式与结构质量由 `word-document-processing` 负责，本技能不运行 P1/P2 深度排版门禁。
