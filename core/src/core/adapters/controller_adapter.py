from core.data import Action, Observation, VehicleState
from core.data.ad_components import Trajectory
from core.interfaces import Controller


class ControllerAdapter:
    """既存のControllerをProcessorとして使えるようにするアダプター."""

    def __init__(self, controller: Controller):
        self.controller = controller

    def process(
        self,
        trajectory: Trajectory,
        vehicle_state: VehicleState,
        observation: Observation | None = None,
    ) -> Action:
        """軌道と車両状態を受け取って制御指令を生成する."""
        return self.controller.control(trajectory, vehicle_state, observation)
