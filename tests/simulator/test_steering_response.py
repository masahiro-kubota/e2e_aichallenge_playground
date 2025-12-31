from pathlib import Path

from core.data import TopicSlot, VehicleParameters, VehicleState
from core.data.autoware import AckermannControlCommand, AckermannLateralCommand, LongitudinalCommand
from core.utils.ros_message_builder import to_ros_time
from simulator.simulator import SimulatorConfig, SimulatorNode


class MockFrameData:
    def __init__(self):
        # Inputs
        self.control_cmd = TopicSlot()
        self.termination_signal = TopicSlot(None)

        # Outputs
        self.sim_state = TopicSlot()
        self.obstacles = TopicSlot()
        self.obstacle_states = TopicSlot()
        self.obstacle_markers = TopicSlot()
        self.perception_lidar_scan = TopicSlot()
        self.steering_status = TopicSlot()


def test_steering_response_integration():
    """Verify that steering response model integrates velocity correctly (SOPDT)."""

    # Setup Parameters
    params = VehicleParameters(
        steer_gain=1.0,  # Unit gain for simple check
        steer_delay_time=0.1,
        steer_omega_n=5.0,
        steer_zeta=0.7,
        max_steer_rate=10.0,  # High limit to avoid saturation
        max_steering_angle=1.0,
        wheelbase=2.7,
        width=1.8,
        vehicle_height=1.5,
        front_overhang=1.0,
        rear_overhang=1.0,
        max_velocity=20.0,
        max_acceleration=5.0,
        lidar=None,
    )

    # Initialize Node
    initial_state = VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=0.0)
    sim_config = SimulatorConfig(
        vehicle_params=params,
        initial_state=initial_state,
        map_path=Path(
            "experiment/assets/lanelet2_map.osm"
        ),  # Dummy path, check not performed if map not used logic
        obstacle_color="#FF0000",
        topic_rates={},
    )

    node = SimulatorNode(config=sim_config, rate_hz=100.0, priority=10)

    # Mock FrameData
    mock_frame = MockFrameData()
    node.set_frame_data(mock_frame)
    node.on_init()

    # Inject Mock Map if needed or ensure it handles missing map
    # SimulatorNode loads map in on_init. If map loading fails, it might error.
    # The snippet uses real map path. For unit test, we might want to mock LaneletMap or provide a minimal map.
    # However, SimulatorNode does: self.map = LaneletMap(Path(self.config.map_path))
    # If file requires existence, we might need a real file.
    # We can perform the test assuming experiment/assets/lanelet2_map.osm exists in the workspace.

    # Step Input
    target_steering = 0.5

    # Run for 1.0 second
    steps = 100
    dt = 0.01

    for i in range(steps):
        t = i * dt

        # Command
        stamp = to_ros_time(t)
        cmd = AckermannControlCommand(
            stamp=stamp,
            lateral=AckermannLateralCommand(stamp=stamp, steering_tire_angle=target_steering),
            longitudinal=LongitudinalCommand(stamp=stamp, acceleration=0.0, speed=0.0),
        )
        mock_frame.control_cmd.update(cmd)

        node.on_run(t)

    # Check Result
    final_steering = node._current_state.actual_steering

    # After 1.0s (delay 0.1s), response should be very close to target (Steady State)
    # Gain is 1.0, so final should be ~0.5
    assert abs(final_steering - target_steering) < 0.05, (
        f"Steering did not settle to target. Target={target_steering}, Actual={final_steering}"
    )

    # Also verify internal rate is NOT zero during transition (hard to check at end, but we can check settled)
    # At steady state, rate should be zero.
    assert abs(node._current_state.steer_rate_internal) < 0.1, (
        "Internal rate should settle to zero at steady state"
    )
