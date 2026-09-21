#!/usr/bin/env python3
"""
从 PDF 提取结构化文本，带分页标注和表格标记。
依赖：pdfplumber
安装：pip install pdfplumber
"""
import argparse
import sys

def extract_pdf(input_path: str, output_path: str) -> None:
    try:
        import pdfplumber
    except ImportError:
        print("[ERROR] 缺少依赖：pip install pdfplumber", file=sys.stderr)
        sys.exit(1)

    chunks = []
    with pdfplumber.open(input_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            chunks.append(f"\n--- 第{i}页 ---\n")
            text = page.extract_text() or ""
            if text.strip():
                chunks.append(text)
            tables = page.extract_tables()
            for table in tables:
                chunks.append("\n[表格内容]\n")
                for row in table:
                    chunks.append(" | ".join(cell or "" for cell in row))
                chunks.append("[表格结束]\n")

    result = "\n".join(chunks)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"[OK] 提取完成，共 {len(result)} 字符 → {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF 文本提取工具")
    parser.add_argument("input", help="PDF 文件路径")
    parser.add_argument("--output", required=True, help="输出文本文件路径")
    args = parser.parse_args()
    extract_pdf(args.input, args.output)
