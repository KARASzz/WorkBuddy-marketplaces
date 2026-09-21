---
title: "DeAI Fingerprint Reference"
summary: "Full AI fingerprint word lists for Chinese, English, Japanese, Korean, plus platform style guides (WeChat, X, Hacker News, Reddit) and colloquial marker vocabularies"
read_when:
  - Editing Japanese or Korean text
  - User specifies a target platform (WeChat, X, HN, Reddit)
  - User asks which filler phrases are removed
  - Checking colloquial marker frequency limits
---

# DeAI 指纹词与平台风格参考库

iLang DeAI 的完整规则表。主流程在专家提示词里，这里放全量查表数据。

## 一、指纹词全表（见到就删）

### 中文（21个）
值得注意的是 / 需要强调的是 / 综上所述 / 不言而喻 / 毋庸置疑 / 显而易见 / 至关重要 / 不可否认 / 总而言之 / 事实上 / 简而言之 / 换句话说 / 从某种意义上说 / 在这个背景下 / 与此同时 / 在很大程度上 / 从本质上讲 / 毫无疑问 / 希望对你有帮助 / 谢谢你的分享 / 让我们一起思考

另：顺序词三连（首先/其次/最后）整组出现时视为指纹，拆掉重组。

### English (16)
Furthermore / It's worth noting that / It is important to note / In conclusion / This demonstrates that / Delve into / Landscape / Leverage (use "use") / Tapestry / Multifaceted (use "complex") / Interestingly / Notably / I hope this helps / In today's world / It's crucial to understand / Let's explore

### 日本語（10）
言うまでもなく / 特筆すべきは / 重要なのは / ～と言えるでしょう / まとめると / 興味深いことに / 注目に値する / お役に立てれば幸いです / ～について探ってみましょう / 総合的に見ると

### 한국어（8）
주목할 만한 것은 / 결론적으로 / 흥미롭게도 / 도움이 되셨길 바랍니다 / 살펴보겠습니다 / 종합적으로 / 중요한 점은 / 의심할 여지 없이

## 二、口语标记词库

| 语言 | 标记模板 | 频率 |
|------|---------|------|
| 中文 | [💬 可加口语：说白了/搞毛/讲真/离谱/我佛了] | 每篇1-3处 |
| English | [💬 add colloquial: tbh/ngl/fwiw/lowkey/honestly] | HN/技术文最多2-4处，Reddit不限 |
| 日本語 | [💬 口語追加：ぶっちゃけ/マジで/ヤバい/草/それな] | 每篇1-3处 |
| 한국어 | [💬 구어체 추가: 솔직히/진짜/대박/ㅋㅋ/아니근데] | 每篇1-3处 |

铁律：AI只标位置，词由用户自己填。AI插的口语有AI味。

## 三、平台风格规范

### 微信公众号
- 第一人称博主口吻，"我跟你说个事"的语气
- 海外品牌用行业简称：Claude→A社、Claude Code→CC、OpenAI→O社、Google→G社、Telegram→电报
- 不用 markdown 标题层级，用**加粗**做段落分隔；bullet 用 • 不用 -
- 段落不超过3行
- 结尾：反问 + 回扣标题 + 评论区引导（只用疑问句，如"评论区聊聊你在用哪个？"）
- 禁止：引导点赞/收藏/转发（有限流风险）、正文放URL、放个人微信号

### X / Twitter
- 旁观记者口吻，第三人称观察
- 结尾定性式，从个案升到系统影响
- 不用表格（不支持），用行内列表
- 可用真名，道德判断嵌在用词里不直说

### Hacker News
- 开发者随笔腔，克制、低调、纯文本零Markdown
- 结尾安静收束（"He shipped. That's what matters."）
- 口语只用 tbh/fwiw；cap/deadass 这类太Gen-Z，不用

### Reddit
- 完全口语化，怎么聊天怎么写
- 所有口语都行
- 结尾一行收掉

## 四、结构修法速查

| AI模式 | 修法 |
|--------|------|
| 长破折号（—/–） | 换逗号或句号 |
| 句长均匀（每句15-25词） | 3词短句和30词长句混排 |
| 分析→论据→结论 | 改成 结论→为什么→论据 |
| 模糊形容词（天价/很多/迅速） | 标[📊]让用户补真实数字 |
| 表演式结尾 | 删，换成结论或真问题 |
| 全文0反问句 | 至少2-3个陈述句改问句 |

## 五、出处

本参考库由 iLang 从作者 200+ 篇实战文章提炼。分享率等数据为作者自有账号的
历史表现，仅作背景说明，不构成效果承诺。
开源仓库：github.com/ilang-ai/ilang-openclaw · 中文站：ilang.cn
