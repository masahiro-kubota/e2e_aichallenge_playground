"""Tests for Simulator Node."""

from core.data import Action, VehicleParameters, VehicleState
from core.data.node_io import NodeIO
from core.interfaces.node import NodeExecutionResult
from simulator.simulator import Simulator


class TestSimulatorNode:
    """Tests for Simulator as a Node."""

    def test_initialization(self) -> None:
        """Test Simulator initialization with config."""
        from simulator.simulator import SimulatorConfig

        config = SimulatorConfig(
            vehicle_params=VehicleParameters(),
            initial_state=VehicleState(x=10.0, y=5.0, yaw=1.0, velocity=2.0, timestamp=0.0),
        )

        sim = Simulator(config=config, rate_hz=10.0)

        assert sim.name == "Simulator"
        assert sim.rate_hz == 10.0
        assert sim.config.initial_state.x == 10.0
        assert sim.config.initial_state.y == 5.0
        assert isinstance(sim.config.vehicle_params, VehicleParameters)

    def test_node_io(self) -> None:
        """Test that Simulator defines correct node IO."""
        from simulator.simulator import SimulatorConfig

        config = SimulatorConfig(vehicle_params=VehicleParameters())
        sim = Simulator(config=config, rate_hz=10.0)

        node_io = sim.get_node_io()

        assert isinstance(node_io, NodeIO)
        assert "action" in node_io.inputs
        assert "sim_state" in node_io.outputs

    def test_on_init(self) -> None:
        """Test on_init initializes state correctly."""
        from simulator.simulator import SimulatorConfig

        config = SimulatorConfig(
            vehicle_params=VehicleParameters(),
            initial_state=VehicleState(x=5.0, y=3.0, yaw=0.5, velocity=1.0, timestamp=0.0),
        )

        sim = Simulator(config=config, rate_hz=10.0)
        sim.on_init()

        # Check internal state is initialized
        assert sim._current_state is not None
        assert sim._current_state.x == 5.0
        assert sim._current_state.y == 3.0
        assert sim.current_time == 0.0
        assert len(sim.log.steps) == 0

    def test_on_run_basic(self) -> None:
        """Test on_run executes physics step."""
        from types import SimpleNamespace

        from simulator.simulator import SimulatorConfig

        config = SimulatorConfig(vehicle_params=VehicleParameters())
        sim = Simulator(config=config, rate_hz=10.0)
        sim.on_init()

        # Create frame data manually
        frame_data = SimpleNamespace()
        frame_data.action = Action(steering=0.1, acceleration=1.0)
        frame_data.termination_signal = False
        sim.set_frame_data(frame_data)

        # Execute
        result = sim.on_run(0.0)

        assert result == NodeExecutionResult.SUCCESS
        assert hasattr(frame_data, "sim_state")
        assert frame_data.sim_state is not None
        assert isinstance(frame_data.sim_state, VehicleState)

    def test_on_run_updates_state(self) -> None:
        """Test that on_run updates vehicle state."""
        from types import SimpleNamespace

        from simulator.simulator import SimulatorConfig

        config = SimulatorConfig(
            vehicle_params=VehicleParameters(),
            initial_state=VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=0.0, timestamp=0.0),
        )
        sim = Simulator(config=config, rate_hz=10.0)
        sim.on_init()

        frame_data = SimpleNamespace()
        frame_data.action = Action(steering=0.0, acceleration=1.0)
        frame_data.termination_signal = False
        sim.set_frame_data(frame_data)

        # Run multiple steps
        for i in range(5):
            result = sim.on_run(i * 0.1)
            assert result == NodeExecutionResult.SUCCESS

        # State should have changed
        final_state = frame_data.sim_state
        assert final_state.velocity > 0.0  # Should have accelerated

    def test_on_run_without_action(self) -> None:
        """Test on_run with no action (should use default)."""
        from types import SimpleNamespace

        from simulator.simulator import SimulatorConfig

        config = SimulatorConfig(vehicle_params=VehicleParameters())
        sim = Simulator(config=config, rate_hz=10.0)
        sim.on_init()

        frame_data = SimpleNamespace()
        frame_data.termination_signal = False
        # Don't set action
        sim.set_frame_data(frame_data)

        result = sim.on_run(0.0)

        # Should still succeed with default action
        assert result == NodeExecutionResult.SUCCESS
        assert frame_data.sim_state is not None

    def test_on_run_with_termination_signal(self) -> None:
        """Test that on_run skips when termination signal is set."""
        from types import SimpleNamespace

        from simulator.simulator import SimulatorConfig

        config = SimulatorConfig(vehicle_params=VehicleParameters())
        sim = Simulator(config=config, rate_hz=10.0)
        sim.on_init()

        frame_data = SimpleNamespace()
        frame_data.termination_signal = True
        sim.set_frame_data(frame_data)

        result = sim.on_run(0.0)

        # Should succeed but not update
        assert result == NodeExecutionResult.SUCCESS

    def test_logging(self) -> None:
        """Test that simulation steps are logged."""
        from types import SimpleNamespace

        from simulator.simulator import SimulatorConfig

        config = SimulatorConfig(vehicle_params=VehicleParameters())
        sim = Simulator(config=config, rate_hz=10.0)
        sim.on_init()

        frame_data = SimpleNamespace()
        frame_data.action = Action(steering=0.1, acceleration=0.5)
        frame_data.termination_signal = False
        sim.set_frame_data(frame_data)

        # Run 3 steps
        for i in range(3):
            sim.on_run(i * 0.1)

        log = sim.get_log()
        assert len(log.steps) == 3

        # Check logged data
        for step in log.steps:
            assert step.timestamp is not None
            assert step.vehicle_state is not None
            assert step.action is not None

    def test_reset_via_on_init(self) -> None:
        """Test that on_init resets state."""
        from types import SimpleNamespace

        from simulator.simulator import SimulatorConfig

        config = SimulatorConfig(vehicle_params=VehicleParameters())
        sim = Simulator(config=config, rate_hz=10.0)
        sim.on_init()

        frame_data = SimpleNamespace()
        frame_data.action = Action(steering=0.0, acceleration=1.0)
        frame_data.termination_signal = False
        sim.set_frame_data(frame_data)

        # Run some steps
        for i in range(5):
            sim.on_run(i * 0.1)

        assert len(sim.log.steps) == 5

        # Reset
        sim.on_init()

        # Log should be cleared
        assert len(sim.log.steps) == 0
        assert sim.current_time == 0.0


class TestSimulatorWithMap:
    """Tests for Simulator with map integration."""

    def test_map_loading(self, tmp_path) -> None:
        """Test that map is loaded when map_path is provided."""
        # Create a minimal OSM file
        osm_content = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="0.0" lon="0.0"/>
  <node id="2" lat="0.0" lon="0.001"/>
  <node id="3" lat="0.001" lon="0.001"/>
  <node id="4" lat="0.001" lon="0.0"/>
  <way id="1">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="3"/>
    <nd ref="4"/>
    <nd ref="1"/>
    <tag k="type" v="lanelet"/>
    <tag k="subtype" v="road"/>
  </way>
</osm>"""

        map_file = tmp_path / "test_map.osm"
        map_file.write_text(osm_content)

        from simulator.simulator import SimulatorConfig

        config = SimulatorConfig(
            vehicle_params=VehicleParameters(),
            map_path=str(map_file),
        )

        sim = Simulator(config=config, rate_hz=10.0)
        sim.on_init()

        # Map should be loaded
        assert sim.map is not None
