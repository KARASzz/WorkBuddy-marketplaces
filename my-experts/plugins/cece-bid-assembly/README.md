# 册册 · 投标文档装册专家（Cece）

从历史标书 / 样板 docx 原位抽取文字与图片素材，按章节定点插回标书 Markdown，渲染为带图 Word，图片零丢失、位置可追溯。

## 类型

Agent 型（单个 AI 专家）· 行业分类：07-SalesCommerce（销售商务）

## 功能

1. **原位抽取**：`docx_parse.py` 解析 docx，输出「标题 → 图片/文字」序列，`section` 字段决定图片归属，不靠文件名猜。
2. **批量插图**：`md_illustrate.py` 按映射表把数百张图一次插入 Markdown 对应章节（先 `--list-sections` 核对，再 dry-run，最后 `--apply`）。
3. **装册渲染**：`md2docx.py` 按册配置 JSON 渲染带封面、表格、图注的 Word（技术册 / 商务册 / 价格册 / 附件册）。
4. **闭环校验**：成品图片数必须与源 docx 引用数一致，差一张回查。

## 目录结构

```
cece-bid-assembly/
├── .codebuddy-plugin/plugin.json
├── agents/cece-bid-assembly.md
├── avatars/expert.png                 # 512×512
├── README.md
└── skills/bid-docx-assembly/
    ├── SKILL.md                       # 5 步流程 + 踩坑清单 + 红线
    ├── scripts/
    │   ├── docx_parse.py              # docx → seq.json
    │   ├── md_illustrate.py           # 映射表 → 插入图片标记
    │   ├── md2docx.py                 # Markdown → Word（需 python-docx）
    │   └── pack_and_upload.sh         # 素材打包单 zip
    └── examples/
        ├── README.md
        ├── haining-yada-ganghua-map.json        # 已投产验证映射表（31 项 / 457 图）
        └── ganghua-sample-doc_sequence.json     # 已验证 seq 基线
```

## 使用示例

- 从历史标书 docx 抽取素材，按章节插回我的标书 Markdown，生成带图 Word
- 解析这份样板 docx，列出全部章节及各自图片数，我要写映射表
- 我的 Markdown 已带图片标记，帮我装册成正式 Word 并核对图片数量

## 依赖

```bash
pip3 install python-docx   # 仅 md2docx.py 需要
zip / unzip                # 仅 pack_and_upload.sh 需要
```

## 头像

头像已自动生成在 `avatars/expert.png`（512×512，452KB）。如需替换：PNG/JPG，512×512，≤500KB。

## 注册

专家包需放在专家目录并注册后才在【专家中心 - 我的专家】可见：

```bash
python3 scripts/register_expert.py <expert-dir>
```

## 打包分享

```bash
zip -r cece-bid-assembly.zip cece-bid-assembly/
```
