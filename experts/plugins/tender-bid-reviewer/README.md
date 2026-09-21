# 标衡 · 招投标审阅专家

一个以 TextIn xParse 为文档证据底座的 WorkBuddy Agent 型专家。它将招标文件、投标文件、证明材料和评审规则识别为不同业务对象，完成可追溯的解读、预审、评分建模和补遗影响分析。

## 核心能力

- 招标文件解读：项目边界、日程、资格、实质性要求、评分规则、合同与履约风险。
- 投标文件预审：完整性、资格、符合性、偏差、证据和内部一致性。
- 评标办法解析：客观评分模型、评分矩阵和多份投标材料的受限比较。
- 补遗与专项审阅：版本影响、技术参数、商务合同、报价/清单核验。

## xParse 机制

当任务需要依据本轮新上传文件作事实判断时，专家必须先使用 WorkBuddy 已启用的 `xparse-parse` Connector Skill；在 WorkBuddy 中所有 CLI 调用使用 `xparse-cli --profile workbuddy`，默认 `--api auto` 免费优先。新文件解析前会基于当前配额和预计页数预警；免费额度不足时提供缩小范围、等待重置或在连接器中安全绑定后明确同意付费的选择。专家包不复制、不配置或保存 xParse 凭据，也不安装或管理 CLI。

## 包内结构

```text
tender-bid-reviewer/
├── .codebuddy-plugin/plugin.json
├── agents/tender-bid-reviewer.md
├── skills/
│   ├── tender-analysis/
│   ├── bid-precheck/
│   ├── bid-evaluation/
│   └── amendment-and-special-review/
├── avatars/
└── tests/acceptance-cases.md
```

## 使用示例

- “请解读这份招标文件，输出资格要求、投标日程、实质性要求和评分策略。”
- “按这份招标文件预审我的投标文件，给出缺失项、待核验项和证据位置。”
- “请把评标办法转成评分矩阵，并说明哪些分数能够从现有材料客观计算。”
- “请比对原招标文件与补遗，列出所有需要同步修改的响应内容。”

## 安装

将包目录置于：

```text
C:\Users\ziheng_chang\.workbuddy\plugins\marketplaces\my-experts\plugins\tender-bid-reviewer\
```

TextIn xParse 依赖通过 `.codebuddy-plugin/plugin.json` 的 `dependencies.connectors` 声明；然后按 WorkBuddy 的专家注册流程校验、注册并刷新市场缓存。

## 重要边界

- 不构成正式法律意见、资格审查结论、评标结论、造价审定或中标承诺。
- 规则随项目类型、地区、行业及招标/采购文件变化；包内法规参考用于提示审阅边界，不替代项目适用规则的人工确认。
- `avatars/expert-market.jpg` 是市场引用的 512×512 JPG 头像，使用“招投标审阅”专家形象；此前 TextIn Logo 文件保留在包内但不由市场配置引用。
