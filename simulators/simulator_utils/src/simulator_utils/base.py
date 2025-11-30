"""Base classes for simulators."""

from abc import ABC
from typing import Any

from core.data import Observation, VehicleState
from core.interfaces import Simulator


class BaseSimulator(Simulator, ABC):
    """シミュレータの基底クラス.

    共通の初期化処理とヘルパーメソッドを提供します。
    """

    def __init__(
        self,
        initial_state: VehicleState | None = None,
        dt: float = 0.1,
    ) -> None:
        """初期化.

        Args:
            initial_state: 初期車両状態
            dt: シミュレーション時間刻み [s]
        """
        self.dt = dt
        self.initial_state = initial_state or VehicleState(
            x=0.0, y=0.0, yaw=0.0, velocity=0.0, timestamp=0.0
        )
        self._current_state = self.initial_state

    def reset(self) -> VehicleState:
        """シミュレーションをリセット.

        Returns:
            初期車両状態
        """
        self._current_state = self.initial_state
        return self._current_state

    def close(self) -> None:
        """シミュレータを終了."""

    def render(self) -> None:
        """シミュレーションを描画(未実装)."""

    def _create_observation(self, state: VehicleState) -> Observation:
        """観測データを生成.

        Args:
            state: 現在の車両状態

        Returns:
            観測データ
        """
        # TODO: Implement proper observation generation based on track/obstacles
        return Observation(
            lateral_error=0.0,
            heading_error=0.0,
            velocity=state.velocity,
            target_velocity=0.0,
            timestamp=state.timestamp,
        )

    def _create_info(self) -> dict[str, Any]:
        """追加情報を生成.

        Returns:
            追加情報の辞書
        """
        return {}

    def _is_done(self) -> bool:
        """エピソード終了判定.

        Returns:
            終了フラグ
        """
        return False
