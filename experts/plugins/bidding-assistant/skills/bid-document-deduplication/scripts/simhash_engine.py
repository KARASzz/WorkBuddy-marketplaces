#!/usr/bin/env python3
"""
SimHash 64-bit 指纹引擎 + Jaccard 相似度计算。

核心算法：
  SimHash:  将文本转为 64-bit 指纹，相似文本 Hamming 距离小
  Jaccard:  基于字符 N-gram 的集合相似度，精确但较慢
  MinHash:  Jaccard 的快速近似估计（用于大规模段落两两比对）

无第三方依赖，仅使用标准库。
"""
import hashlib
import re
from typing import List, Tuple, Set


# ── 文本预处理 ────────────────────────────────────────────────────────────────

# 需过滤的无意义字符（保留中英文、数字，去除标点/空白）
_NOISE_RE = re.compile(r"[\s　﻿​，。！？；：、\"'（）【】《》…—,.!?;:()\[\]-]+")


def normalize(text: str) -> str:
    """去除噪声字符，返回紧凑文本。"""
    return _NOISE_RE.sub('', text)


def char_ngrams(text: str, n: int = 3) -> List[str]:
    """生成字符 N-gram 列表（中文适配）。"""
    t = normalize(text)
    if len(t) < n:
        return [t] if t else []
    return [t[i:i+n] for i in range(len(t) - n + 1)]


def char_ngram_set(text: str, n: int = 3) -> Set[str]:
    """生成字符 N-gram 集合（用于 Jaccard 计算）。"""
    return set(char_ngrams(text, n))


# ── SimHash ───────────────────────────────────────────────────────────────────

HASH_BITS = 64


def _token_hash(token: str) -> int:
    """将 token 映射为 64-bit 无符号整数。"""
    return int(hashlib.md5(token.encode('utf-8', errors='replace')).hexdigest()[:16], 16)


def simhash(text: str, n: int = 3) -> int:
    """
    计算文本的 64-bit SimHash 指纹。
    输入：文本字符串
    输出：64-bit 整数指纹
    """
    tokens = char_ngrams(text, n)
    if not tokens:
        return 0

    # 每个 bit 位的加权累计
    v = [0] * HASH_BITS
    for token in tokens:
        h = _token_hash(token)
        for i in range(HASH_BITS):
            if (h >> i) & 1:
                v[i] += 1
            else:
                v[i] -= 1

    # 生成最终指纹
    fingerprint = 0
    for i in range(HASH_BITS):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def hamming_distance(fp1: int, fp2: int) -> int:
    """计算两个 64-bit 指纹的 Hamming 距离（不同 bit 数）。"""
    xor = fp1 ^ fp2
    # Brian Kernighan 算法计数
    count = 0
    while xor:
        xor &= xor - 1
        count += 1
    return count


def simhash_similarity(fp1: int, fp2: int) -> float:
    """
    将 Hamming 距离转换为相似度 [0, 1]。
    Hamming=0 → 1.0（完全相同）
    Hamming=64 → 0.0（完全不同）
    """
    return 1.0 - hamming_distance(fp1, fp2) / HASH_BITS


# ── Jaccard 相似度 ────────────────────────────────────────────────────────────

def jaccard_similarity(text_a: str, text_b: str, n: int = 3) -> float:
    """
    计算两段文本的 Jaccard 相似度（基于字符 N-gram 集合）。
    J(A,B) = |A ∩ B| / |A ∪ B|
    """
    set_a = char_ngram_set(text_a, n)
    set_b = char_ngram_set(text_b, n)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union


# ── MinHash（大规模段落快速近似） ─────────────────────────────────────────────

_LARGE_PRIME = (1 << 61) - 1   # 梅森素数

def _minhash_params(num_hashes: int):
    """生成 MinHash 的 a, b 参数列表（固定种子，可复现）。"""
    import random
    rng = random.Random(42)
    return [
        (rng.randint(1, _LARGE_PRIME - 1), rng.randint(0, _LARGE_PRIME - 1))
        for _ in range(num_hashes)
    ]


_DEFAULT_NUM_HASHES = 128
_MINHASH_AB = _minhash_params(_DEFAULT_NUM_HASHES)


def minhash_signature(text: str, n: int = 3) -> List[int]:
    """计算文本的 MinHash 签名向量（长度 = _DEFAULT_NUM_HASHES）。"""
    shingles = char_ngram_set(text, n)
    if not shingles:
        return [_LARGE_PRIME] * _DEFAULT_NUM_HASHES

    sig = [_LARGE_PRIME] * _DEFAULT_NUM_HASHES
    for shingle in shingles:
        h = _token_hash(shingle) % _LARGE_PRIME
        for i, (a, b) in enumerate(_MINHASH_AB):
            hv = (a * h + b) % _LARGE_PRIME
            if hv < sig[i]:
                sig[i] = hv
    return sig


def minhash_similarity(sig_a: List[int], sig_b: List[int]) -> float:
    """由 MinHash 签名估计 Jaccard 相似度。"""
    if len(sig_a) != len(sig_b) or not sig_a:
        return 0.0
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a)


# ── 综合相似度 ────────────────────────────────────────────────────────────────

def similarity_score(text_a: str, text_b: str,
                     use_minhash: bool = False) -> Tuple[float, str]:
    """
    综合相似度计算。
    短文本（< 200 字）用 Jaccard；长文本用 MinHash 快速估计。
    返回 (相似度 0-1, 使用的算法名称)。
    """
    min_len = min(len(text_a), len(text_b))
    if min_len == 0:
        return 0.0, "empty"

    if use_minhash or min_len > 500:
        sig_a = minhash_signature(text_a)
        sig_b = minhash_signature(text_b)
        return minhash_similarity(sig_a, sig_b), "minhash"
    else:
        return jaccard_similarity(text_a, text_b), "jaccard"


# ── 相似度等级 ────────────────────────────────────────────────────────────────

def similarity_level(score: float) -> str:
    """将相似度数值转为等级标签。"""
    if score >= 0.95:
        return "近似重复"
    elif score >= 0.60:
        return "高度相似"
    elif score >= 0.30:
        return "中度相似"
    elif score >= 0.10:
        return "低度相似"
    else:
        return "基本不同"


def hamming_level(dist: int) -> str:
    """将 Hamming 距离转为等级标签（用于 SimHash 全文比对）。"""
    if dist <= 3:
        return "近似重复"
    elif dist <= 10:
        return "高度相似"
    elif dist <= 20:
        return "中度相似"
    else:
        return "基本不同"


# ── 自测 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    t1 = "本公司具有多年信息系统集成经验，拥有完善的质量管理体系和专业技术团队。"
    t2 = "本公司拥有多年信息系统集成经验，具备完善的质量管理体系和专业的技术团队。"
    t3 = "深圳市市政道路改造项目预算已经通过审批，施工单位即将进场。"

    fp1, fp2, fp3 = simhash(t1), simhash(t2), simhash(t3)
    print(f"t1 vs t2 Hamming={hamming_distance(fp1,fp2)}  "
          f"Jaccard={jaccard_similarity(t1,t2):.3f}  level={similarity_level(jaccard_similarity(t1,t2))}")
    print(f"t1 vs t3 Hamming={hamming_distance(fp1,fp3)}  "
          f"Jaccard={jaccard_similarity(t1,t3):.3f}  level={similarity_level(jaccard_similarity(t1,t3))}")
