"""Scene and track boundary data structures."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.data.environment.obstacle import Obstacle


@dataclass
class Scene:
    """シミュレーション環境全体.

    トラック情報と障害物を管理。
    """

    track: None = None  # 将来の拡張用(現在未使用)
    obstacles: list[Obstacle] = field(default_factory=list)  # 障害物リスト
