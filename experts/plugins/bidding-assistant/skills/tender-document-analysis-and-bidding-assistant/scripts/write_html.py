#!/usr/bin/env python3
"""
将 HTML 字符串写入文件（Claude 生成 HTML 后调用此脚本保存）。
无外部依赖。
"""
import argparse
import sys
from pathlib import Path


def write_html(html_content: str, output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    size_kb = Path(output_path).stat().st_size / 1024
    print(f"[OK] HTML 工作台已生成 → {output_path}（{size_kb:.1f} KB）")
    if size_kb > 5120:
        print("[WARN] 文件超过 5MB，建议精简 CSS/JS 或拆分模块", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="写入 HTML 文件")
    parser.add_argument("--html-file", help="包含 HTML 内容的临时文件路径（与 --html-content 二选一）")
    parser.add_argument("--html-content", help="HTML 字符串内容（与 --html-file 二选一）")
    parser.add_argument("--output", required=True, help="输出 .html 文件路径")
    args = parser.parse_args()

    if args.html_file:
        with open(args.html_file, encoding="utf-8") as f:
            content = f.read()
    elif args.html_content:
        content = args.html_content
    else:
        print("[ERROR] 请提供 --html-file 或 --html-content", file=sys.stderr)
        sys.exit(1)

    write_html(content, args.output)
