"""加载招投标共享的偏离表原子化规则。"""
from __future__ import annotations

import importlib.util
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2] / "_shared" / "deviation_atomic.py"


def _load_shared_module():
    spec = importlib.util.spec_from_file_location("_bidding_deviation_atomic", SOURCE)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载共享偏离表规则: {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_shared_module()

for NAME in dir(MODULE):
    if not NAME.startswith("_"):
        globals()[NAME] = getattr(MODULE, NAME)
