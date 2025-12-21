from typing import Any

from core.data import ComponentConfig, VehicleState
from core.data.node_io import NodeIO
from core.interfaces.node import Node, NodeExecutionResult


class IdealSensorConfig(ComponentConfig):
    pass


class IdealSensorNode(Node[IdealSensorConfig]):
    """理想的なセンサーノード (ノイズなし、遅延なし)."""

    def __init__(
        self, config: IdealSensorConfig, rate_hz: float, vehicle_params: Any | None = None
    ):
        super().__init__("Sensor", rate_hz, config)
        _ = vehicle_params

    def get_node_io(self) -> NodeIO:
        return NodeIO(inputs={"sim_state": VehicleState}, outputs={"vehicle_state": VehicleState})

    def on_run(self, _current_time: float) -> NodeExecutionResult:
        if self.frame_data is None:
            return NodeExecutionResult.FAILED

        sim_state = getattr(self.frame_data, "sim_state", None)
        if sim_state is None:
            return NodeExecutionResult.SKIPPED

        # Pass through
        self.frame_data.vehicle_state = sim_state
        return NodeExecutionResult.SUCCESS
