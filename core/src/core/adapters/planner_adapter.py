from core.data import Observation, VehicleState
from core.data.ad_components import Trajectory
from core.interfaces import Planner


class PlannerAdapter:
    """既存のPlannerをProcessorとして使えるようにするアダプター."""

    def __init__(self, planner: Planner):
        self.planner = planner

    def process(self, vehicle_state: VehicleState, observation: Observation) -> Trajectory:
        """車両状態と観測情報を受け取って軌道を生成する."""
        return self.planner.plan(observation, vehicle_state)
