"""Tests for SimulationVehicleState."""

from core.data import Action, VehicleState
from simulator.state import SimulationVehicleState


class TestSimulationVehicleState:
    """Tests for SimulationVehicleState."""

    def test_from_vehicle_state(self) -> None:
        """Test conversion from VehicleState."""
        vehicle_state = VehicleState(
            x=10.0,
            y=20.0,
            yaw=1.57,
            velocity=5.0,
            acceleration=1.0,
            steering=0.5,
            timestamp=100.0,
        )

        dynamic_state = SimulationVehicleState.from_vehicle_state(vehicle_state)

        assert dynamic_state.x == 10.0
        assert dynamic_state.y == 20.0
        assert dynamic_state.z == 0.0
        assert dynamic_state.yaw == 1.57
        assert dynamic_state.roll == 0.0
        assert dynamic_state.pitch == 0.0

        # Velocity decomposition (yaw is ignored in conversion, vx = velocity, vy = 0)
        assert abs(dynamic_state.vx - 5.0) < 1e-10
        assert dynamic_state.vy == 0.0
        assert dynamic_state.vz == 0.0

        assert dynamic_state.ax == 1.0
        assert dynamic_state.steering == 0.5
        assert dynamic_state.timestamp == 100.0

    def test_to_vehicle_state(self) -> None:
        """Test conversion to VehicleState."""
        dynamic_state = SimulationVehicleState(
            x=10.0,
            y=20.0,
            z=5.0,
            roll=0.1,
            pitch=0.2,
            yaw=1.57,
            vx=3.0,
            vy=4.0,  # Velocity = 5.0
            vz=0.0,
            ax=0.5,
            steering=0.1,
            timestamp=100.0,
        )

        # Test without action
        vehicle_state = dynamic_state.to_vehicle_state()

        assert vehicle_state.x == 10.0
        assert vehicle_state.y == 20.0
        assert vehicle_state.yaw == 1.57
        assert abs(vehicle_state.velocity - 5.0) < 1e-10  # sqrt(3^2 + 4^2)
        assert vehicle_state.acceleration == 0.5
        assert vehicle_state.steering == 0.1
        assert vehicle_state.timestamp == 100.0

        # Test with action
        action = Action(steering=0.2, acceleration=1.0)
        vehicle_state_with_action = dynamic_state.to_vehicle_state(action)

        assert vehicle_state_with_action.acceleration == 1.0
        assert vehicle_state_with_action.steering == 0.2
        # Other fields should remain same
        assert vehicle_state_with_action.x == 10.0


class TestSimulationVehicleStateProperties:
    """Tests for SimulationVehicleState properties."""

    def test_velocity_property(self) -> None:
        """Test 3D velocity magnitude calculation."""
        state = SimulationVehicleState(
            x=0.0,
            y=0.0,
            vx=3.0,
            vy=4.0,
            vz=0.0,
        )

        # velocity = sqrt(3^2 + 4^2 + 0^2) = 5.0
        assert abs(state.velocity - 5.0) < 1e-10

    def test_velocity_2d_property(self) -> None:
        """Test 2D velocity magnitude calculation."""
        state = SimulationVehicleState(
            x=0.0,
            y=0.0,
            vx=3.0,
            vy=4.0,
            vz=12.0,  # Should be ignored in 2D calculation
        )

        # velocity_2d = sqrt(3^2 + 4^2) = 5.0
        assert abs(state.velocity_2d - 5.0) < 1e-10

    def test_velocity_with_all_components(self) -> None:
        """Test velocity with all three components."""
        state = SimulationVehicleState(
            x=0.0,
            y=0.0,
            vx=1.0,
            vy=2.0,
            vz=2.0,
        )

        # velocity = sqrt(1^2 + 2^2 + 2^2) = 3.0
        assert abs(state.velocity - 3.0) < 1e-10

    def test_beta_property(self) -> None:
        """Test slip angle calculation."""
        state = SimulationVehicleState(
            x=0.0,
            y=0.0,
            vx=5.0,
            vy=5.0,
        )

        # beta = atan2(vy, vx) = atan2(5, 5) = pi/4
        import math

        expected_beta = math.atan2(5.0, 5.0)
        assert abs(state.beta - expected_beta) < 1e-10

    def test_beta_at_zero_velocity(self) -> None:
        """Test slip angle at zero velocity."""
        state = SimulationVehicleState(
            x=0.0,
            y=0.0,
            vx=0.0,
            vy=5.0,
        )

        # At zero vx, beta should be 0
        assert abs(state.beta) < 1e-10

    def test_beta_with_negative_vx(self) -> None:
        """Test slip angle with negative vx."""
        state = SimulationVehicleState(
            x=0.0,
            y=0.0,
            vx=-5.0,
            vy=5.0,
        )

        import math

        expected_beta = math.atan2(5.0, -5.0)
        assert abs(state.beta - expected_beta) < 1e-10


class TestSimulationVehicleStateEdgeCases:
    """Tests for edge cases in SimulationVehicleState."""

    def test_all_zero_state(self) -> None:
        """Test state with all zeros."""
        state = SimulationVehicleState(x=0.0, y=0.0)

        assert state.x == 0.0
        assert state.y == 0.0
        assert state.z == 0.0
        assert state.velocity == 0.0
        assert state.velocity_2d == 0.0
        assert state.beta == 0.0

    def test_negative_velocity_components(self) -> None:
        """Test with negative velocity components."""
        state = SimulationVehicleState(
            x=0.0,
            y=0.0,
            vx=-3.0,
            vy=-4.0,
            vz=0.0,
        )

        # Magnitude should still be positive
        assert abs(state.velocity - 5.0) < 1e-10
        assert abs(state.velocity_2d - 5.0) < 1e-10

    def test_timestamp_none(self) -> None:
        """Test state without timestamp."""
        state = SimulationVehicleState(
            x=1.0,
            y=2.0,
            timestamp=None,
        )

        assert state.timestamp is None

        # Conversion should preserve None timestamp
        vehicle_state = state.to_vehicle_state()
        assert vehicle_state.timestamp is None

    def test_roundtrip_conversion_preserves_data(self) -> None:
        """Test that roundtrip conversion preserves essential data."""
        original = VehicleState(
            x=10.0,
            y=20.0,
            yaw=1.5,
            velocity=5.0,
            acceleration=1.0,
            steering=0.3,
            timestamp=100.0,
        )

        # Convert to SimulationVehicleState and back
        sim_state = SimulationVehicleState.from_vehicle_state(original)
        restored = sim_state.to_vehicle_state()

        # Check essential fields are preserved
        assert restored.x == original.x
        assert restored.y == original.y
        assert restored.yaw == original.yaw
        assert abs(restored.velocity - original.velocity) < 1e-10
        assert restored.acceleration == original.acceleration
        assert restored.steering == original.steering
        assert restored.timestamp == original.timestamp
