"""
Model Registry — 从 models/ 目录加载已训练的模型

用法:
    from src.models.registry import list_models, load_model

    # 列出所有可用模型版本
    versions = list_models()
    # → [{"version": "V1", "name": "28stock_fwd21", "target": "forward_return_21", ...}, ...]

    # 加载模型
    model = load_model("V1")          # 加载 default (final) 模型
    model = load_model("V1", "W1")    # 加载指定窗口模型
    model = load_model("V1", "final") # 明确加载 final

    # 加载 OOS 预测
    pred = load_predictions("V1")
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict

import pandas as pd
import lightgbm as lgb

logger = logging.getLogger(__name__)

MODELS_ROOT = Path(__file__).resolve().parent.parent.parent / "models"


def list_models() -> List[Dict]:
    """列出 models/ 下所有已注册的模型版本。"""
    if not MODELS_ROOT.exists():
        return []
    versions = []
    for d in sorted(MODELS_ROOT.iterdir()):
        if d.is_dir() and (d / "manifest.json").exists():
            with open(d / "manifest.json", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest["dir"] = str(d)
            versions.append(manifest)
    return versions


def load_model(version: str, window: str = "final") -> lgb.Booster:
    """
    加载指定版本的 LightGBM 模型。

    Parameters
    ----------
    version : str
        版本标识，如 "V1"，会匹配 models/V1_*/ 目录。
    window : str
        窗口名，如 "W1", "W2", "final"。默认 "final"。
    """
    model_dir = _resolve_version(version)
    model_path = model_dir / "models" / f"{window}.txt"
    if not model_path.exists():
        raise FileNotFoundError(
            f"模型文件不存在: {model_path}，可用窗口: {list((model_dir/'models').glob('*.txt'))}"
        )
    model = lgb.Booster(model_file=str(model_path))
    logger.info(f"  Model loaded: {model_path}")
    return model


def load_predictions(version: str) -> pd.DataFrame:
    """
    加载指定版本的 OOS 预测。
    """
    model_dir = _resolve_version(version)
    pred_path = model_dir / "oos_predictions.parquet"
    if not pred_path.exists():
        raise FileNotFoundError(f"OOS 预测不存在: {pred_path}")
    return pd.read_parquet(pred_path)


def load_manifest(version: str) -> Dict:
    """加载指定版本的 manifest 元信息。"""
    model_dir = _resolve_version(version)
    with open(model_dir / "manifest.json", encoding="utf-8") as f:
        return json.load(f)


def _resolve_version(version: str) -> Path:
    """解析版本号到实际目录。"""
    if not MODELS_ROOT.exists():
        raise FileNotFoundError(f"models/ 目录不存在: {MODELS_ROOT}")
    for d in MODELS_ROOT.iterdir():
        if d.is_dir() and d.name.startswith(version + "_"):
            return d
    available = [d.name for d in MODELS_ROOT.iterdir() if d.is_dir()]
    raise ValueError(
        f"找不到版本 '{version}'，可用: {available}"
    )