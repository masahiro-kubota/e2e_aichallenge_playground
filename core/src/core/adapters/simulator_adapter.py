from core.data import Action, VehicleState
from core.interfaces import Simulator


class SimulatorAdapter:
    """既存のSimulatorをProcessorとして使えるようにするアダプター."""

    def __init__(self, simulator: Simulator):
        self.simulator = simulator

    def process(self, action: Action) -> VehicleState:
        """アクションを受け取ってシミュレーターをステップ実行し、状態を返す."""
        state, _, _ = self.simulator.step(action)
        return state
