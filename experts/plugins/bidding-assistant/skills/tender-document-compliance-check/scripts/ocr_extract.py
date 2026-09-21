#!/usr/bin/env python3
"""
招投标 OCR 文本提取模块。

当 PDF/扫描件通过 pdfplumber 提取内容不足（< MIN_CHARS 字）时，
自动调用 RicheeAI OCR API 进行识别，参考法大大专用 OCR 技能实现模式。

环境变量：
  RICHEEAI_TOKEN        — 认证 Token（由 RicheeAI cowork 会话自动注入）
  RICHEEAI_API_BASE     — API 基础域名（默认 https://claw.richee.cn/claw-api）
  RICHEEAI_OCR_ENDPOINT — OCR 接口路径（默认 /ocr/file/parse）

用法（作为模块导入）：
    from ocr_extract import extract_with_ocr_fallback
    text, method = extract_with_ocr_fallback("/path/to/scan.pdf")
    # method: "local" | "ocr_api" | "failed"

用法（命令行独立运行）：
    python ocr_extract.py /path/to/scan.pdf --output /tmp/ocr_text.txt
"""

import json
import os
import sys
import time
from pathlib import Path

# 将本目录加入路径，以便导入 proxy_utils
_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))

from proxy_utils import get_auth_token, get_api_base_url, make_request

# ── 配置 ──────────────────────────────────────────────────────
MIN_CHARS = 500          # 低于此字数视为扫描件/不可提取
OCR_TIMEOUT = 120        # OCR API 超时（秒）
OCR_DEFAULT_ENDPOINT = "/ocr/file/parse"   # 可通过环境变量覆盖


def get_ocr_endpoint() -> str:
    return os.environ.get("RICHEEAI_OCR_ENDPOINT", OCR_DEFAULT_ENDPOINT)


# ── 本地提取（pdfplumber / python-docx）──────────────────────

def _try_local_docx(path: str) -> str:
    """用 python-docx 提取 .docx 全文。"""
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""


def _try_local_pdf(path: str) -> str:
    """用 pdfplumber 提取 PDF 全文。"""
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t.strip():
                    pages.append(t)
        return "\n".join(pages)
    except Exception:
        return ""


def _try_local_txt(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def try_local_extract(file_path: str) -> str:
    """
    尝试本地提取文本，返回提取到的文字（可能为空字符串）。
    """
    suffix = Path(file_path).suffix.lower()
    if suffix == ".docx":
        return _try_local_docx(file_path)
    elif suffix == ".pdf":
        return _try_local_pdf(file_path)
    else:
        return _try_local_txt(file_path)


# ── RicheeAI OCR API 调用 ─────────────────────────────────────

def call_ocr_api(file_path: str) -> dict:
    """
    上传文件至 RicheeAI OCR API，返回识别结果。

    请求格式（参考法大大上传合同实现）：
      POST {API_BASE}{OCR_ENDPOINT}
      Content-Type: multipart/form-data
      richee-token: {RICHEEAI_TOKEN}
      Body: file 字段（文件二进制）

    响应格式（期望）：
      {"success": true, "data": {"text": "全文", "pages": [{"page": 1, "text": "..."}]}}
      或
      {"code": "000000", "data": "全文字符串"}

    Returns:
        {"success": True, "text": "...", "pages": [...]}
        {"success": False, "error": "..."}
    """
    token = get_auth_token()
    if not token:
        return {"success": False, "error": "未找到 RICHEEAI_TOKEN，无法调用 OCR API"}

    base_url  = get_api_base_url()
    endpoint  = get_ocr_endpoint()
    url       = f"{base_url}{endpoint}"
    file_name = Path(file_path).name

    # 读取文件内容
    try:
        with open(file_path, "rb") as f:
            file_content = f.read()
    except Exception as e:
        return {"success": False, "error": f"读取文件失败：{e}"}

    # 构造 multipart/form-data（同法大大 upload_contract 模式）
    boundary = "----RicheeOCRBoundary8MA4YWxkTrZu0gW"
    parts = []
    parts.append((
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8"))
    parts.append(file_content)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)

    headers = {
        "richee-token":  token,
        "User-Agent":    "Mozilla/5.0 RicheeAI-BidOCR/1.0",
        "Accept":        "application/json",
        "Content-Type":  f"multipart/form-data; boundary={boundary}",
    }

    print(f"[ocr] 调用 RicheeAI OCR API：{url}", file=sys.stderr)
    raw = make_request(url, headers, body, "POST", timeout=OCR_TIMEOUT)

    # make_request 失败时返回 dict
    if isinstance(raw, dict):
        return {"success": False, "error": raw.get("error", "请求失败")}

    # 解析 JSON 响应
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as e:
        return {"success": False, "error": f"OCR 响应解析失败：{e}"}

    # 兼容多种响应格式
    is_ok = parsed.get("success") or parsed.get("callSuccess")
    code  = parsed.get("code")
    if not is_ok:
        is_ok = code in (200, "200", "000000", 0, "0")

    if not is_ok:
        return {
            "success": False,
            "error": parsed.get("message") or parsed.get("msg", "OCR 识别失败"),
            "code": code
        }

    data = parsed.get("data", {})

    # 响应 data 可能是字符串（纯文本）或字典（含 text/pages）
    if isinstance(data, str):
        return {"success": True, "text": data, "pages": []}
    elif isinstance(data, dict):
        text  = data.get("text") or data.get("content") or data.get("result") or ""
        pages = data.get("pages") or data.get("pageList") or []
        # 若无 text 但有 pages，拼接
        if not text and pages:
            text = "\n".join(
                p.get("text") or p.get("content") or "" for p in pages
            )
        return {"success": True, "text": text, "pages": pages}
    else:
        return {"success": False, "error": f"未知 data 格式：{type(data)}"}


# ── 智能提取入口 ──────────────────────────────────────────────

def extract_with_ocr_fallback(file_path: str,
                               min_chars: int = MIN_CHARS,
                               force_ocr: bool = False) -> tuple:
    """
    智能文本提取：本地优先，扫描件自动调用 OCR API。

    Args:
        file_path:  文件路径（.pdf / .docx / .txt / 图片等）
        min_chars:  本地提取内容低于此字数时触发 OCR（默认 500）
        force_ocr:  True = 跳过本地提取，直接调 OCR API

    Returns:
        (text: str, method: str)
          method: "local"     — 本地提取成功
                  "ocr_api"   — OCR API 识别成功
                  "failed"    — 均失败，text 为空字符串或错误说明
    """
    suffix = Path(file_path).suffix.lower()

    # 非 PDF/图片的 docx 直接本地提取（不走 OCR）
    if not force_ocr and suffix == ".docx":
        text = _try_local_docx(file_path)
        if len(text) >= min_chars:
            print(f"[ocr] 本地提取成功（{len(text)} 字）", file=sys.stderr)
            return text, "local"
        # docx 内容不足时也尝试 OCR（可能是图文混排）

    # 尝试本地提取
    if not force_ocr:
        text = try_local_extract(file_path)
        if len(text) >= min_chars:
            print(f"[ocr] 本地提取成功（{len(text)} 字）", file=sys.stderr)
            return text, "local"
        print(f"[ocr] 本地提取内容不足（{len(text)} 字 < {min_chars}），触发 OCR API",
              file=sys.stderr)

    # 调用 OCR API
    result = call_ocr_api(file_path)
    if result.get("success"):
        text = result.get("text", "")
        pages = result.get("pages", [])
        print(f"[ocr] OCR API 成功（{len(text)} 字，{len(pages)} 页）",
              file=sys.stderr)
        return text, "ocr_api"
    else:
        err = result.get("error", "未知错误")
        print(f"[ocr] OCR API 失败：{err}", file=sys.stderr)
        # 返回本地提取的少量文字（宁可有缺陷也好过完全空）
        local_text = try_local_extract(file_path) if not force_ocr else ""
        return local_text, "failed"


# ── 命令行入口 ────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="招投标 OCR 文本提取（本地优先 + API 降级）"
    )
    parser.add_argument("file", help="待提取文件路径（.pdf / .docx / 图片等）")
    parser.add_argument("--output", "-o", default="",
                        help="输出文本文件路径（默认打印到 stdout）")
    parser.add_argument("--force-ocr", action="store_true",
                        help="跳过本地提取，直接调用 OCR API")
    parser.add_argument("--min-chars", type=int, default=MIN_CHARS,
                        help=f"触发 OCR 的最小字数阈值（默认 {MIN_CHARS}）")
    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"[error] 文件不存在：{args.file}", file=sys.stderr)
        sys.exit(1)

    text, method = extract_with_ocr_fallback(
        args.file,
        min_chars=args.min_chars,
        force_ocr=args.force_ocr
    )

    status = "✓" if method != "failed" else "✗"
    print(f"[{status}] 提取方式：{method}，字数：{len(text)}", file=sys.stderr)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"[done] 文本已写入 {args.output}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
