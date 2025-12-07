"""Autonomous driving component interfaces."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from core.data import Action, Observation, VehicleParameters, VehicleState
from core.data.ad_components import Trajectory

if TYPE_CHECKING:
    from core.interfaces.node import Node


class ADComponent(ABC):
    """自動運転コンポーネントの統合インターフェース.

    ノードプロバイダーとして機能し、実行可能なノードのリストを提供する。
    具体的なノード構成は各実装クラスで定義する。
    """

    def __init__(self, vehicle_params: VehicleParameters, **_kwargs: Any) -> None:
        """初期化.

        Args:
            vehicle_params: 車両パラメータ
            **_kwargs: コンポーネント固有のパラメータ
        """
        self.vehicle_params = vehicle_params

    @abstractmethod
    def get_schedulable_nodes(self) -> list["Node"]:
        """スケジュール可能なノードのリストを返す.

        Returns:
            List of Nodes to be executed by the executor.
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset the component."""


class Perception(ABC):
    """認識コンポーネントの抽象基底クラス."""

    @abstractmethod
    def perceive(self, sensor_data: Any) -> Observation:
        """センサーデータから観測を生成.

        Args:
            sensor_data: センサーデータ(カメラ画像、LiDARなど)

        Returns:
            Observation: 観測データ
        """

    @abstractmethod
    def reset(self) -> None:
        """認識コンポーネントをリセット."""


class Planner(ABC):
    """計画コンポーネントの抽象基底クラス."""

    @abstractmethod
    def plan(
        self,
        observation: Observation,
        vehicle_state: VehicleState,
    ) -> Trajectory:
        """観測と車両状態から軌道を生成.

        Args:
            observation: 観測データ
            vehicle_state: 車両状態

        Returns:
            Trajectory: 計画された軌道
        """

    @abstractmethod
    def reset(self) -> None:
        """計画コンポーネントをリセット."""


class Controller(ABC):
    """制御コンポーネントの抽象基底クラス."""

    @abstractmethod
    def control(
        self,
        trajectory: Trajectory,
        vehicle_state: VehicleState,
        observation: Observation | None = None,
    ) -> Action:
        """軌道と車両状態から制御指令を生成.

        Args:
            trajectory: 目標軌道
            vehicle_state: 車両状態
            observation: 観測データ(オプション)

        Returns:
            Action: 制御指令
        """

    @abstractmethod
    def reset(self) -> None:
        """制御コンポーネントをリセット."""
