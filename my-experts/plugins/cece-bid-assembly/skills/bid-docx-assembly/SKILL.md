---
name: bid-docx-assembly
description: "投标文档装册与素材复用工具 - 从历史标书/样板 docx 原位提取文字与图片素材，按章节定点插回新建标书 Markdown，并渲染为带图的 Word。关键词：标书装册、素材抽取、docx 解析、定点插图、Markdown 转 Word、标书图片、批量上传"
version: "1.0.0"
author: "WorkBuddy"
created: "2026-09-07"
updated: "2026-09-07"
---

# 投标文档装册与素材复用（bid-docx-assembly）

> **Goal**: 把"从样板/历史标书抽取素材 → 按章节定点插回新标书 → 渲染带图 Word"这一整套流程标准化，
> **不重新造轮子、不逐张上传图片刷爆 token、不遗漏素材、不错位插图**。

## When to Use

触发场景：
- 用户要求"从样板/历史标书抽取素材"、"把图片放进标书"、"组装最终版/正式版 Word"
- 需要生成带图片的投标文档（技术册/商务册/价格册/附件册）
- 需要把几百张素材图归入对应章节（禁止逐张人工挑图）
- 需要把 Markdown 过程成果装册为 Word

**不触发**：单张图片查看、纯文字润色、与装册无关的文档编辑。

---

## 核心原则（必须遵守）

1. **原位复刻优先**：图片插到哪里，由**样板原文的图片位置**决定，不靠人工想象、不靠文件名猜。
   解析 docx 得到"标题→图片"序列后按映射插入，位置可复现、可追溯。
2. **绝不逐张上传图片**：几百张图逐个调用上传 = token 爆炸。
   正确做法：打包成单个 zip，一次上传（脚本 3）。操作次数 N → 1。
3. **Markdown 是唯一事实源**：图片以 `![图注](路径)` 标记写在 Markdown 里，
   Word 由 Markdown 渲染生成。**不要绕过 Markdown 直接改 Word**。
4. **占位符保留，不伪装完成**：价格、签章、待澄清项等在成品中显式保留占位标记与提示，
   不得静默删除或用推测值填充。
5. **图片用绝对路径写死在 Markdown 中**（渲染器支持绝对路径），交付前如需迁移再统一替换。

---

## 完整流程（5 步）

### 步骤 1：解析源 docx → 正文序列 JSON

```bash
python3 scripts/docx_parse.py <样板.docx> -o seq.json
```

输出 JSON 每项：
- `{"type":"TXT","text":"...","section":"所属标题"}`
- `{"type":"IMG","rid":"rId8","media":"media/image1.jpeg","section":"所属标题"}`

**关键**：`section` 字段 = 该图出现时最近的标题，这是"原位复刻"的唯一依据。

自检：核对输出末尾的统计，确认 `唯一图片数` 与 `word/media/` 目录文件数一致。

### 步骤 2：图片入库到持久目录

```bash
mkdir -p <项目>/01-素材库镜像/图片素材-media原号
cp <解压目录>/word/media/* <项目>/01-素材库镜像/图片素材-media原号/
```

- **保留 media 原号**（image1.jpeg…），与 seq.json 一一对应，便于回溯
- 不要依赖 `/tmp` 等临时目录，正式产物会被清理
- 分类归档（A/B/C/D 档）+ 写一份索引 Markdown 是可选增强，但**原位插入不依赖分类目录**

### 步骤 3：编写映射表 → 插入图片标记

映射表 JSON（一个文件可含多个目标 md）：

```json
{
  "技术册.md": [
    ["样板中的标题名", "目标md中的锚点标题", "图注前缀"]
  ],
  "商务册.md": [
    ["（2）专利", "维度①：企业综合实力", "专利证书"]
  ]
}
```

#### 3a. 先看清有哪些 section（**不可跳过**）

```bash
python3 scripts/md_illustrate.py --seq seq.json --map map.json --media-dir <图片目录> --list-sections
```

输出每个 section 名 + 含图数。**照着这个清单写映射表**，不要凭记忆或猜测。

> ⚠️ **最大坑**：docx 的"标题"判定没有万能规则。同一份 docx 用不同模式解析，
> section 名和数量会变（实测：同一文档 legacy 60 个 / strict 48 个 / 人工校准 31 个）。
> 解析脚本只能保证**图片不丢**（457 引用 / 446 唯一文件恒定），
> 但**不保证 section 划分与原作者意图一致**。
> 所以：写映射表前必须 `--list-sections` 核对；若关键 section 被拆散，
> 用 `--mode strict` 重解析，或复用 `examples/` 中已验证的基线。

#### 3b. dry-run 核对锚点

```bash
python3 scripts/md_illustrate.py --seq seq.json --map map.json \
  --media-dir <图片目录> --base-dir <md所在目录>
```

脚本会在 section 对不上时**自动提示最相近的候选**（含图数），照提示改映射表即可。

#### 3c. 写入

```bash
python3 scripts/md_illustrate.py --seq seq.json --map map.json \
  --media-dir <图片目录> --base-dir <md所在目录> --apply
```

自动备份为 `.bak`。

锚点匹配规则：支持 `##` / `###` 标题，也支持 `**粗体**` 段落（如 `**维度①：企业综合实力**`）。
**映射表里的锚点写纯标题文本，不要带 `###` 前缀或 `**` 符号**——这是最常见的错误。

### 步骤 4：渲染 Word

写册配置 JSON，然后：

```bash
python3 scripts/md2docx.py --config config.json
```

配置示例见 `scripts/md2docx.py` 顶部注释。支持：标题、表格、图片、引用提示、列表、代码块、YAML 头跳过。

### 步骤 5：验证

```python
from docx import Document
from docx.oxml.ns import qn
doc = Document('输出.docx')
print('图片数:', len(doc.element.body.findall('.//' + qn('a:blip'))))
```

**必须验证**：Word 中图片数 == 步骤 1 统计的图片引用数。差一张都要回查。

---

## 踩过的坑（血泪清单）

| 坑 | 现象 | 正确做法 |
|---|---|---|
| 映射表锚点带 `###` 前缀 | 全部提示"锚点未找到"，插图 0 张 | 锚点写**纯标题文本**，脚本内部已剥离 `#` 和 `*` |
| **标题自动判定不可靠** | 同一 docx 解析出 31/48/60 个 section，映射表失效 | **`--list-sections` 核对后写映射表**；图片数恒定，section 划分不保证 |
| 加严判定导致丢关键 section | "（2）专利"27 图、"①内控手册"193 图 消失 | 用 `--mode legacy`（默认）保底；必要时复用已验证基线 |
| 逐张上传图片 | 417 张图 token 爆炸 | 打包 zip 单次上传（脚本 3） |
| 临时目录存图 | `/tmp` 被清理后图片全失效 | 入库到项目持久目录 |
| 靠文件名猜图片内容 | 分类错、插错位 | 用 `section` 字段（原位关系），不猜 |
| 用 `--data-binary` 不带 `@` 上传 | 上传空文件/失败 | 用 `-T "文件"` 流式上传 |
| 只分类归档、不做原位映射 | 无法知道每图该插哪节 | 归档之外必须保留 seq.json |
| 文件字节数相同≠同一文件 | 误判重复跳过上传 | 字节数+内容双查；命名错误要以内容为准 |
| 直接改 Word 不改 Markdown | 下次重生成就丢失 | Markdown 是唯一事实源 |
| 分类归档漏文件 | 归档 417 张但 media 有 446 张 | 入库时以**完整 media 目录**为准，不依赖分类目录 |

---

## 红线（禁止）

- 禁止编造/推测图片归属章节——以 seq.json 的 `section` 为准
- 禁止为"让文档好看"删除占位符或填入未确认的数值
- 禁止把含客户抬头、合同金额、证照原件的素材图外发到第三方接口/公共链接
- 禁止在人工门禁未通过时，把过程版伪装成正式递交版（封面必须显式标注版本性质）

---

## 脚本清单

| 脚本 | 作用 | 输入 → 输出 |
|---|---|---|
| `scripts/docx_parse.py` | 解析 docx，保留标题→图片原位关系 | docx → seq.json |
| `scripts/md_illustrate.py` | 按映射把图片标记插入 Markdown 章节 | seq.json + map.json → 修改 md |
| `scripts/md2docx.py` | 通用 Markdown→Word 渲染器（支持图片） | config.json → docx |
| `scripts/pack_and_upload.sh` | 大批量素材打包为单 zip | 源目录 → zip |

## 可复用样例

`examples/haining-yada-ganghua-map.json`
— 已投产验证的完整映射表（31 项 / 457 图全部正确插入）。
新项目编写映射表时直接照抄结构；同类项目（燃气 PE 管材）可复用大部分映射。
详见 `examples/README.md`。

## 依赖

```bash
pip3 install python-docx   # 仅 md2docx.py 需要
zip / unzip                # 仅 pack_and_upload.sh 需要
```

## 一句话心法

> **图片不丢靠脚本，位置不错靠核对。**
> 脚本能保证 457 张图一张不少地进文档；但"每张图该待在哪一节"，
> 必须 `--list-sections` 之后人工确认——这一步省不得，省了就得返工。
