"""Configuration file utilities."""

from pathlib import Path
from typing import Any

import yaml


def load_yaml(file_path: str | Path) -> dict[str, Any]:
    """YAMLファイルを読み込む.

    Args:
        file_path: YAMLファイルのパス

    Returns:
        読み込んだ設定辞書

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        yaml.YAMLError: YAMLのパースエラー
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config if config is not None else {}


def save_yaml(data: dict[str, Any], file_path: str | Path) -> None:
    """YAMLファイルに保存.

    Args:
        data: 保存するデータ
        file_path: 保存先のパス
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)


def merge_configs(
    base_config: dict[str, Any],
    override_config: dict[str, Any],
) -> dict[str, Any]:
    """設定を再帰的にマージ.

    Args:
        base_config: ベース設定
        override_config: 上書き設定

    Returns:
        マージされた設定
    """
    merged = base_config.copy()

    for key, value in override_config.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            # 辞書の場合は再帰的にマージ
            merged[key] = merge_configs(merged[key], value)
        else:
            # それ以外は上書き
            merged[key] = value

    return merged


def get_nested_value(
    config: dict[str, Any],
    key_path: str,
    default: Any | None = None,
    separator: str = ".",
) -> Any:
    """ネストされた設定値を取得.

    Args:
        config: 設定辞書
        key_path: キーのパス（例: "simulator.vehicle.wheelbase"）
        default: デフォルト値
        separator: キーの区切り文字

    Returns:
        設定値、存在しない場合はdefault

    Example:
        >>> config = {"simulator": {"vehicle": {"wheelbase": 2.5}}}
        >>> get_nested_value(config, "simulator.vehicle.wheelbase")
        2.5
    """
    keys = key_path.split(separator)
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def set_nested_value(
    config: dict[str, Any],
    key_path: str,
    value: Any,
    separator: str = ".",
) -> None:
    """ネストされた設定値を設定.

    Args:
        config: 設定辞書
        key_path: キーのパス（例: "simulator.vehicle.wheelbase"）
        value: 設定する値
        separator: キーの区切り文字

    Example:
        >>> config = {}
        >>> set_nested_value(config, "simulator.vehicle.wheelbase", 2.5)
        >>> config
        {'simulator': {'vehicle': {'wheelbase': 2.5}}}
    """
    keys = key_path.split(separator)
    current = config

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value


__all__ = [
    "get_nested_value",
    "load_yaml",
    "merge_configs",
    "save_yaml",
    "set_nested_value",
]
