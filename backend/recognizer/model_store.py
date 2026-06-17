"""
模型存储与路径解析：支持「软件内更新模型」(走 GitHub Releases)。

加载策略：
  用户数据目录 (可写，下载的新模型) 优先 → 回退打包内置 (只读、随 App 分发)。
  内置模型永远存在 → 离线 / 下载失败都能用，不会变砖。

目录：
  - 内置模型：backend/models/                （PyInstaller 打包随 App，只读）
  - 用户模型：平台标准用户数据目录/models/    （可写，存下载的更新）
      Windows: %APPDATA%/xiangqi-endgame/models
      macOS:   ~/Library/Application Support/xiangqi-endgame/models
      Linux:   ~/.local/share/xiangqi-endgame/models
  均可被环境变量覆盖：
      XIANGQI_MODEL_DIR        → 直接指定用户模型目录
      XIANGQI_MODELS_MANIFEST  → 模型更新 manifest 地址 (models.json)

版本记录：用户模型目录下 version.json {"version": N}
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

APP_NAME = "xiangqi-endgame"
MODEL_FILES = ("piece_classifier.onnx", "board_locator.onnx")
LABELS_FILE = "labels.txt"

# 模型更新 manifest 默认地址（请改成你的仓库 Release，或用 env 覆盖）
DEFAULT_MANIFEST_URL = (
    "https://github.com/your-org/xiangqi-endgame/releases/latest/download/models.json"
)


def bundled_model_dir() -> str:
    """打包内置模型目录 (backend/models)。"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")


def _platform_data_dir() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_NAME)


def user_model_dir(create: bool = False) -> str:
    """用户可写模型目录（下载的更新存这里）。"""
    d = os.environ.get("XIANGQI_MODEL_DIR") or os.path.join(_platform_data_dir(), "models")
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def resolve_model(filename: str) -> str:
    """
    解析某模型文件的实际加载路径：用户目录有就用用户目录，否则回退内置。
    返回的路径不保证存在（内置也可能没有该文件，由调用方判断）。
    """
    u = os.path.join(user_model_dir(), filename)
    if os.path.isfile(u):
        return u
    return os.path.join(bundled_model_dir(), filename)


def model_source(filename: str) -> str:
    """该模型当前来自 'user'(已更新) / 'bundled'(内置) / 'missing'。"""
    if os.path.isfile(os.path.join(user_model_dir(), filename)):
        return "user"
    if os.path.isfile(os.path.join(bundled_model_dir(), filename)):
        return "bundled"
    return "missing"


def manifest_url() -> str:
    return os.environ.get("XIANGQI_MODELS_MANIFEST") or DEFAULT_MANIFEST_URL


def _version_path() -> str:
    return os.path.join(user_model_dir(), "version.json")


def local_version() -> int:
    """已安装的下载模型版本；未更新过返回 0（视为内置基线）。"""
    try:
        with open(_version_path(), encoding="utf-8") as f:
            return int(json.load(f).get("version", 0))
    except Exception:
        return 0


def set_local_version(version: int) -> None:
    user_model_dir(create=True)
    with open(_version_path(), "w", encoding="utf-8") as f:
        json.dump({"version": int(version)}, f)


def installed_models_info() -> dict:
    """各模型来源 + 当前下载版本，供 /model/status。"""
    return {
        "version": local_version(),
        "user_model_dir": user_model_dir(),
        "sources": {fn: model_source(fn) for fn in MODEL_FILES},
        "manifest_url": manifest_url(),
    }
