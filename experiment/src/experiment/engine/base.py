from abc import ABC, abstractmethod
from typing import Any

from omegaconf import DictConfig


class BaseEngine(ABC):
    """実験フェーズの基底クラス"""

    @abstractmethod
    def run(self, cfg: DictConfig) -> Any:
        """エンジンを実行

        Args:
            cfg: Hydra設定オブジェクト
        """
        pass
