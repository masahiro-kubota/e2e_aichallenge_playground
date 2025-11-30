"""Kinematic bicycle model simulator implementation."""

from typing import Any

from core.data import Action, Observation, VehicleState
from simulator_kinematic.vehicle import KinematicVehicleModel
from simulator_utils.base import BaseSimulator


class KinematicSimulator(BaseSimulator):
    """キネマティック自転車モデルに基づく軽量2Dシミュレータ."""

    def __init__(
        self,
        initial_state: VehicleState | None = None,
        dt: float = 0.1,
        wheelbase: float = 2.5,
    ) -> None:
        """初期化.

        Args:
            initial_state: 初期車両状態
            dt: シミュレーション時間刻み [s]
            wheelbase: ホイールベース [m]
        """
        super().__init__(initial_state=initial_state, dt=dt)
        self.vehicle_model = KinematicVehicleModel(wheelbase=wheelbase)

    def step(self, action: Action) -> tuple[VehicleState, Observation, bool, dict[str, Any]]:
        """1ステップ実行.

        Args:
            action: 制御指令

        Returns:
            vehicle_state: 更新された車両状態
            observation: 観測データ
            done: エピソード終了フラグ
            info: 追加情報
        """
        self._current_state = self.vehicle_model.step(
            state=self._current_state,
            steering=action.steering,
            acceleration=action.acceleration,
            dt=self.dt,
        )

        observation = self._create_observation(self._current_state)
        done = self._is_done()
        info = self._create_info()

        return self._current_state, observation, done, info
