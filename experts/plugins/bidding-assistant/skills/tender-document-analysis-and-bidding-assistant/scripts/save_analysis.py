#!/usr/bin/env python3
"""
将解析结果 JSON 字符串写入文件，供后续脚本读取。
无第三方依赖。

用法：
  python scripts/save_analysis.py \
      --data '{"overview": {...}, ...}' \
      --output /tmp/tender_analysis.json

  # 或从文件读取（管道场景）：
  cat /tmp/raw.json | python scripts/save_analysis.py --stdin --output /tmp/tender_analysis.json
"""
import argparse
import json
import sys
from pathlib import Path

from analysis_schema import normalize_analysis, print_audit


def main():
    parser = argparse.ArgumentParser(description="保存招标解析 JSON 数据")
    parser.add_argument("--data",   help="JSON 字符串")
    parser.add_argument("--stdin",  action="store_true", help="从 stdin 读取 JSON")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    args = parser.parse_args()

    if args.stdin:
        raw = sys.stdin.read()
    elif args.data:
        raw = args.data
    else:
        print("[ERROR] 请提供 --data 或 --stdin", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败：{e}", file=sys.stderr)
        sys.exit(1)

    data, audit = normalize_analysis(data, include_aliases=True)
    print_audit(audit)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 解析数据已保存 → {args.output}")


if __name__ == "__main__":
    main()
