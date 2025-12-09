from typing import Any

from core.data import Action, ADComponentLog
from core.data.node_io import NodeIO
from core.interfaces import Simulator
from core.interfaces.node import Node


class PhysicsNode(Node):
    """Node responsible for stepping the simulator physics."""

    def __init__(self, simulator: Simulator, config: Any):
        if config.execution is None:
            raise ValueError("Execution config is required")

        # Extract values from config
        sim_rate = config.simulator.rate_hz
        goal_radius = config.execution.goal_radius

        super().__init__("Physics", sim_rate)
        self.simulator = simulator
        self.step_count = 0
        self.goal_radius = goal_radius

    def get_node_io(self) -> NodeIO:
        from core.data import Action, Trajectory, VehicleState

        return NodeIO(
            inputs={
                "action": Action,
                "trajectory": Trajectory,
            },
            outputs={
                "sim_state": VehicleState,
                "done": bool,
                "done_reason": str,
                "success": bool,
            },
        )

    def on_run(self, _current_time: float) -> bool:
        if self.frame_data is None:
            # FrameData not ready
            return False

        if self.frame_data.done:
            return True

        # Use previous action or default
        action = self.frame_data.action or Action(steering=0.0, acceleration=0.0)

        # Step simulator
        state, done, info = self.simulator.step(action)
        self.step_count += 1

        # Inject detailed AD logs into the simulation step
        if hasattr(self.simulator, "log") and self.simulator.log.steps:
            step_log = self.simulator.log.steps[-1]

            # Create data dictionary
            data: dict[str, Any] = {}
            if self.frame_data.trajectory:
                # We save the trajectory points
                data["trajectory"] = [
                    {"x": p.x, "y": p.y, "velocity": p.velocity}
                    for p in self.frame_data.trajectory.points
                ]

            step_log.ad_component_log = ADComponentLog(component_type="split_nodes", data=data)

        # Update ground truth state
        self.frame_data.sim_state = state

        # Check termination conditions
        # 1. Simulator native done (collision, etc)
        if done:
            self.frame_data.done = True
            self.frame_data.done_reason = "simulator_done"
            self.frame_data.success = False
            return True

        # 2. Off track
        if state.off_track:
            self.frame_data.done = True
            self.frame_data.done_reason = "off_track"
            self.frame_data.success = False
            return True

        # 3. Goal checking (if supported by simulator)
        if hasattr(self.simulator, "goal_x") and hasattr(self.simulator, "goal_y"):
            goal_x = getattr(self.simulator, "goal_x")
            goal_y = getattr(self.simulator, "goal_y")

            if goal_x is not None and goal_y is not None:
                dist = ((state.x - goal_x) ** 2 + (state.y - goal_y) ** 2) ** 0.5
                if dist < self.goal_radius:
                    self.frame_data.done = True
                    self.frame_data.done_reason = "goal_reached"
                    self.frame_data.success = True
                    return True

        return True
