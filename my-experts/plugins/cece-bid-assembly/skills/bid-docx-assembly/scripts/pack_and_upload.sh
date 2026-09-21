#!/usr/bin/env bash
# pack_and_upload.sh — 大批量素材打包为单个 zip（供 Drive/网盘一次性上传）
#
# 背景教训：逐张上传几百张图片会瞬间刷爆上下文 token。
# 正确做法：本地打包成 1 个 zip → 单次流式上传 → 落库 1 次，操作次数从 N 降到 1。
#
# 用法：
#   bash pack_and_upload.sh <源目录> <输出zip路径> [--exclude "*.bak"]
#
# 说明：
# - 只负责"打包"，上传动作由调用方使用网盘/Drive 工具完成（保持脚本与传输解耦）
# - 打包前打印统计：文件数、总大小，便于预估上传耗时
# - 建议单包 < 500MB；超大素材可分卷（见下方 split 提示）

set -euo pipefail

SRC="${1:-}"
OUT="${2:-}"
EXCLUDE="${3:-}"

if [[ -z "$SRC" || -z "$OUT" ]]; then
  echo "用法: bash pack_and_upload.sh <源目录> <输出zip路径> [排除模式]"
  exit 1
fi

if [[ ! -d "$SRC" ]]; then
  echo "错误: 源目录不存在: $SRC"
  exit 1
fi

mkdir -p "$(dirname "$OUT")"

echo "== 统计 =="
NFILES=$(find "$SRC" -type f | wc -l | tr -d ' ')
SIZE=$(du -sh "$SRC" | cut -f1)
echo "  文件数: $NFILES"
echo "  总大小: $SIZE"
echo ""

echo "== 打包 =="
if [[ -n "$EXCLUDE" ]]; then
  (cd "$(dirname "$SRC")" && zip -qr "$OUT" "$(basename "$SRC")" -x "$EXCLUDE")
else
  (cd "$(dirname "$SRC")" && zip -qr "$OUT" "$(basename "$SRC")")
fi

OUTSIZE=$(du -h "$OUT" | cut -f1)
echo "  已生成: $OUT ($OUTSIZE)"
echo ""

if (( $(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT") > 524288000 )); then
  echo "!! 提示: 单包超过 500MB，建议分卷上传："
  echo "   zip -s 400m -r ${OUT%.zip}.zip $(basename "$SRC")"
fi

echo "== 下一步（由调用方执行）=="
echo "  1) 调用网盘/Drive 上传工具获取临时上传 URL + headers"
echo "  2) curl -sSL -X PUT -H <headers> -T \"$OUT\" \"<上传URL>\""
echo "     注意：必须 -T（流式文件），禁止 --data-binary 不带 @"
echo "  3) 调用 upload_complete 落库（传 confirm_key + task_id）"
echo ""
echo "  如需解压后保留目录结构，接收方用 unzip 即可（本脚本按相对路径打包）。"
