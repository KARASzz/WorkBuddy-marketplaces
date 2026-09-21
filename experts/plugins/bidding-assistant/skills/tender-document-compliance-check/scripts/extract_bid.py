#!/usr/bin/env python3
"""
提取投标文件文本及章节结构，输出：
  --output      /tmp/bid_raw.txt          全文纯文本
  --structure   /tmp/bid_structure.json   一级标题列表 + 各节字数

支持 Word (.docx) 和 PDF (.pdf)。
依赖：python-docx / pdfplumber（与招标解析工具共享）
"""
import argparse, json, re, sys
from pathlib import Path

# 单技能打包模式：OCR/API 辅助脚本随本技能放在 scripts/ 目录内。
_LOCAL_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_LOCAL_SCRIPTS))

MIN_CHARS_OCR = 500   # 低于此字数触发 OCR 降级


# ── Word 提取 ─────────────────────────────────
def extract_word(path: str):
    try:
        from docx import Document
    except ImportError:
        sys.exit("[ERROR] 缺少依赖：pip install python-docx")

    doc = Document(path)
    lines, sections = [], []
    current_title, current_chars = None, 0

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        # 识别一级标题（Heading 1 样式，或"第X章/部分"格式）
        is_h1 = (para.style.name.startswith("Heading 1") or
                 re.match(r'^(第[一二三四五六七八九十百\d]+[章节部分条]|[一二三四五六七八九十]+、|\d+\.|（[一二三四五六七八九十]+）)', text))
        if is_h1:
            if current_title:
                sections.append({"title": current_title, "char_count": current_chars})
            current_title, current_chars = text, 0
        lines.append(text)
        current_chars += len(text)

    if current_title:
        sections.append({"title": current_title, "char_count": current_chars})

    # 提取表格
    for table in doc.tables:
        lines.append("\n[表格内容]")
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
        lines.append("[表格结束]")

    return "\n".join(lines), sections


# ── PDF 提取 ──────────────────────────────────
def extract_pdf(path: str):
    try:
        import pdfplumber
    except ImportError:
        sys.exit("[ERROR] 缺少依赖：pip install pdfplumber")

    lines, sections = [], []
    h1_pattern = re.compile(
        r'^(第[一二三四五六七八九十百\d]+[章节部分条]|[一二三四五六七八九十]+、|\d+\.\s)'
    )
    current_title, current_chars = None, 0

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            lines.append(f"\n--- 第{i}页 ---")
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if h1_pattern.match(line):
                    if current_title:
                        sections.append({"title": current_title, "char_count": current_chars})
                    current_title, current_chars = line, 0
                lines.append(line)
                current_chars += len(line)

            for table in (page.extract_tables() or []):
                lines.append("\n[表格内容]")
                for row in table:
                    lines.append(" | ".join(cell or "" for cell in row))
                lines.append("[表格结束]")

    if current_title:
        sections.append({"title": current_title, "char_count": current_chars})

    return "\n".join(lines), sections


# ── 入口 ──────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="投标文件文本提取工具")
    parser.add_argument("input", help="投标文件路径（.docx 或 .pdf）")
    parser.add_argument("--format", choices=["word", "pdf", "auto"], default="auto",
                        help="文件格式，auto 根据扩展名自动判断")
    parser.add_argument("--output", required=True, help="全文输出路径（.txt）")
    parser.add_argument("--structure", default="/tmp/bid_structure.json",
                        help="结构输出路径（.json）")
    args = parser.parse_args()

    fmt = args.format
    if fmt == "auto":
        ext = Path(args.input).suffix.lower()
        fmt = "pdf" if ext == ".pdf" else "word"

    if fmt == "word":
        text, sections = extract_word(args.input)
    else:
        text, sections = extract_pdf(args.input)

    # OCR 降级：扫描件 / 加密 PDF 本地提取内容不足时调用 API 识别
    if len(text) < MIN_CHARS_OCR:
        print(f"[WARN] 本地提取内容不足（{len(text)} 字），尝试 OCR 降级…", file=sys.stderr)
        try:
            from ocr_extract import extract_with_ocr_fallback
            ocr_text, method = extract_with_ocr_fallback(args.input, min_chars=MIN_CHARS_OCR)
            if method in ("local", "ocr_api") and len(ocr_text) > len(text):
                print(
                    f"[OCR] 已通过 {method} 重新提取（{len(ocr_text)} 字）",
                    file=sys.stderr,
                )
                text = ocr_text
                # OCR 返回纯文本，重置章节结构
                sections = []
            else:
                print(f"[WARN] OCR 未能提升内容量（method={method}，{len(ocr_text)} 字）",
                      file=sys.stderr)
        except Exception as e:
            print(f"[OCR] 降级失败，使用本地提取结果：{e}", file=sys.stderr)

    if len(text) < MIN_CHARS_OCR:
        print(f"[WARN] 最终提取内容仍不足（{len(text)} 字），可能为加密文件或 OCR 失败",
              file=sys.stderr)

    Path(args.output).write_text(text, encoding="utf-8")
    Path(args.structure).write_text(
        json.dumps({"sections": sections, "total_chars": len(text),
                    "section_count": len(sections)}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"[OK] 提取完成：{len(text)} 字符，{len(sections)} 个章节 → {args.output}")


if __name__ == "__main__":
    main()
