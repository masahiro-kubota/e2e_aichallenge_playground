"""Dynamic bicycle model simulator implementation."""

import math
from typing import Any

from simulator_core.base import BaseSimulator
from simulator_core.integration import rk4_step

from core.data import Action, VehicleParameters, VehicleState
from simulator_dynamic.state import DynamicVehicleState
from simulator_dynamic.vehicle import DynamicVehicleModel


class DynamicSimulator(BaseSimulator):
    """ダイナミック自転車モデルに基づく2Dシミュレータ."""

    def __init__(
        self,
        vehicle_params: "VehicleParameters | None" = None,
        initial_state: VehicleState | None = None,
        dt: float = 0.01,  # Smaller dt for RK4 stability
        params: Any | None = None,  # 後方互換性のため
    ) -> None:
        """初期化.

        Args:
            vehicle_params: 車両パラメータ
            initial_state: 初期車両状態(キネマティクス形式)
            dt: シミュレーション時間刻み [s]
            params: レガシーパラメータ（非推奨）
        """
        # 後方互換性: paramsが指定されている場合はvehicle_paramsとして扱う
        if params is not None and vehicle_params is None:
            vehicle_params = params

        super().__init__(vehicle_params=vehicle_params, initial_state=initial_state, dt=dt)

        self.vehicle_model = DynamicVehicleModel(params=self.vehicle_params)

        # Convert kinematic state to dynamic state
        self._dynamic_state = self._kinematic_to_dynamic(self.initial_state)

    def reset(self) -> VehicleState:
        """シミュレーションをリセット.

        Returns:
            初期車両状態
        """
        super().reset()
        self._dynamic_state = self._kinematic_to_dynamic(self.initial_state)
        return self._current_state

    def _update_state(self, action: Action) -> VehicleState:
        """Update vehicle state using RK4 integration.

        Args:
            action: Control action

        Returns:
            Updated vehicle state
        """
        # Convert acceleration to throttle (simplified)
        throttle = action.acceleration / 5.0  # Normalize to [-1, 1] range
        throttle = max(-1.0, min(1.0, throttle))

        # Dynamic update using RK4
        def derivative_func(state: DynamicVehicleState) -> DynamicVehicleState:
            return self.vehicle_model.calculate_derivative(state, action.steering, throttle)

        self._dynamic_state = rk4_step(
            state=self._dynamic_state,
            derivative_func=derivative_func,
            dt=self.dt,
            add_func=self.vehicle_model.add_state,
        )

        # Convert dynamic state back to kinematic state
        return self._dynamic_to_kinematic(self._dynamic_state, action.steering, action.acceleration)

    def _kinematic_to_dynamic(self, state: VehicleState) -> DynamicVehicleState:
        """キネマティクス状態をダイナミクス状態に変換.

        Args:
            state: キネマティクス状態

        Returns:
            ダイナミクス状態
        """
        # Assume no lateral velocity initially
        vx = state.velocity * math.cos(0.0)  # beta = 0
        vy = state.velocity * math.sin(0.0)

        return DynamicVehicleState(
            x=state.x,
            y=state.y,
            yaw=state.yaw,
            vx=vx,
            vy=vy,
            yaw_rate=0.0,
            steering=state.steering or 0.0,
            throttle=0.0,
            timestamp=state.timestamp,
        )

    def _dynamic_to_kinematic(
        self, state: DynamicVehicleState, steering: float, acceleration: float
    ) -> VehicleState:
        """ダイナミクス状態をキネマティクス状態に変換.

        Args:
            state: ダイナミクス状態
            steering: ステアリング角
            acceleration: 加速度

        Returns:
            キネマティクス状態
        """
        return VehicleState(
            x=state.x,
            y=state.y,
            yaw=state.yaw,
            velocity=state.velocity,
            acceleration=acceleration,
            steering=steering,
            timestamp=state.timestamp,
        )
