#!/usr/bin/env python3
"""
RicheeAI LLM API 调用模块（投标合规语义评审专用）。

环境变量：
  RICHEEAI_TOKEN         — 认证 Token（RicheeAI cowork 会话自动注入）
  RICHEEAI_API_BASE      — API 基础域名（默认 https://claw.richee.cn/claw-api）
  RICHEEAI_LLM_ENDPOINT  — LLM 接口路径（默认 /ai/v1/chat/completions）
  RICHEEAI_LLM_MODEL     — 使用的模型（默认 deepseek-v3）

用法：
    from llm_client import chat_completion, extract_json_from_llm
    resp = chat_completion([
        {"role": "system", "content": "你是专业的投标文件审查专家"},
        {"role": "user",   "content": "请判断..."},
    ])
    if resp["success"]:
        data = extract_json_from_llm(resp["content"])
"""

import json
import os
import re
import sys

from proxy_utils import get_auth_token, get_api_base_url, make_json_request

LLM_TIMEOUT          = 60       # 单次调用超时（秒）
LLM_DEFAULT_ENDPOINT = "/ai/v1/chat/completions"
LLM_DEFAULT_MODEL    = "deepseek-v3"


def get_llm_config() -> tuple:
    """返回 (url, model)。"""
    base  = get_api_base_url()
    ep    = os.environ.get("RICHEEAI_LLM_ENDPOINT", LLM_DEFAULT_ENDPOINT)
    model = os.environ.get("RICHEEAI_LLM_MODEL",    LLM_DEFAULT_MODEL)
    return f"{base}{ep}", model


def chat_completion(messages: list,
                    temperature: float = 0.1,
                    max_tokens: int = 1200) -> dict:
    """
    调用 RicheeAI LLM Chat API（OpenAI 兼容格式）。

    Args:
        messages:    OpenAI 格式消息列表 [{"role": ..., "content": ...}, ...]
        temperature: 温度（评审场景建议 0.1，保证低随机性）
        max_tokens:  最大输出 token 数

    Returns:
        {"success": True,  "content": "回复文本"}
        {"success": False, "error":   "错误原因"}
    """
    token = get_auth_token()
    if not token:
        return {"success": False,
                "error": "未找到 RICHEEAI_TOKEN，无法调用 LLM API"}

    url, model = get_llm_config()
    headers = {
        "richee-token": token,
        "Content-Type": "application/json",
        "Accept":       "application/json",
        "User-Agent":   "Mozilla/5.0 RicheeAI-BidEval/1.0",
    }
    payload = {
        "model":       model,
        "messages":    messages,
        "temperature": temperature,
        "max_tokens":  max_tokens,
        "stream":      False,
    }

    print(f"[llm] POST {url}  model={model}", file=sys.stderr)
    result = make_json_request(url, headers, payload, "POST", timeout=LLM_TIMEOUT)

    # make_json_request 失败时返回 {"error": ...}（无 "choices" 键）
    if isinstance(result, dict) and "error" in result and "choices" not in result:
        return {"success": False, "error": result.get("error", "请求失败")}

    try:
        # ── OpenAI 标准格式 ──────────────────────────────────────
        if isinstance(result, dict) and "choices" in result:
            content = result["choices"][0]["message"]["content"]
            return {"success": True, "content": content}

        # ── RicheeAI 自研格式兼容 ────────────────────────────────
        ok   = result.get("success") or result.get("callSuccess")
        code = result.get("code")
        if not ok:
            ok = code in (200, "200", "000000", 0, "0")
        if not ok:
            return {"success": False,
                    "error": result.get("message") or result.get("msg", "LLM 调用失败")}

        data = result.get("data", "")
        if isinstance(data, str):
            return {"success": True, "content": data}
        content = (data.get("content") or data.get("text") or
                   data.get("answer") or data.get("result") or "")
        return {"success": True, "content": content}

    except Exception as e:
        return {"success": False,
                "error": f"响应解析异常：{e}，原始：{str(result)[:200]}"}


def extract_json_from_llm(text: str) -> dict:
    """
    从 LLM 响应文本中提取第一个 JSON 对象。
    兼容三种格式：
      1. 纯 JSON
      2. ```json ... ``` markdown 代码块
      3. JSON 前后有说明文字（取最外层 { ... }）
    """
    if not text:
        return {}

    # 1. markdown 代码块
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 2. 最外层花括号
    m = re.search(r'\{[\s\S]+\}', text)
    candidate = m.group(0) if m else text
    try:
        return json.loads(candidate)
    except Exception:
        return {}
