"""Tests for InitialStateSampler."""

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from experiment.engine.initial_state_sampler import InitialStateSampler


class TestInitialStateSampler:
    """Tests for InitialStateSampler class."""

    @pytest.fixture
    def track_path(self) -> Path:
        """Get path to test track CSV."""
        return Path("experiment/assets/raceline_awsim_15km.csv")

    @pytest.fixture
    def map_path(self) -> Path:
        """Get path to test map OSM."""
        return Path("experiment/assets/lanelet2_map.osm")

    @pytest.fixture
    def sampler(self, track_path: Path, map_path: Path) -> "InitialStateSampler":
        """Create InitialStateSampler instance."""
        from experiment.engine.initial_state_sampler import InitialStateSampler
        from simulator.map import LaneletMap

        lanelet_map = LaneletMap(map_path)
        return InitialStateSampler(track_path, lanelet_map)

    def test_load_track(self, sampler: "InitialStateSampler") -> None:
        """Test that track is loaded correctly."""
        assert len(sampler.track_data) > 0
        assert "x" in sampler.track_data.columns
        assert "y" in sampler.track_data.columns
        assert "yaw" in sampler.track_data.columns

    def test_sample_initial_state(self, sampler: "InitialStateSampler") -> None:
        """Test basic sampling functionality."""
        rng = np.random.default_rng(42)
        state = sampler.sample_initial_state(
            rng=rng,
            lateral_offset_range=(-2.0, 2.0),
            yaw_offset_range=(-0.2, 0.2),
            velocity_range=(5.0, 15.0),
            max_retries=10,
        )

        assert "x" in state
        assert "y" in state
        assert "yaw" in state
        assert "velocity" in state
        assert 5.0 <= state["velocity"] <= 15.0

    def test_sample_multiple_states(self, sampler: "InitialStateSampler") -> None:
        """Test that multiple samples produce different states."""
        rng = np.random.default_rng(42)
        states = [
            sampler.sample_initial_state(
                rng=rng,
                lateral_offset_range=(-2.0, 2.0),
                yaw_offset_range=(-0.2, 0.2),
                velocity_range=(5.0, 15.0),
                max_retries=10,
            )
            for _ in range(5)
        ]

        # Check that states are different
        x_values = [s["x"] for s in states]
        assert len(set(x_values)) > 1, "All x positions are the same"

    def test_lateral_offset_applied(self, sampler: "InitialStateSampler") -> None:
        """Test that lateral offset is correctly applied."""
        rng = np.random.default_rng(42)
        state = sampler.sample_initial_state(
            rng=rng,
            lateral_offset_range=(0.0, 0.0),  # No offset
            yaw_offset_range=(0.0, 0.0),
            velocity_range=(10.0, 10.0),
            max_retries=10,
        )

        # With zero offset, position should be on centerline
        # Find closest centerline point
        distances = np.sqrt(
            (sampler.track_data["x"] - state["x"]) ** 2
            + (sampler.track_data["y"] - state["y"]) ** 2
        )
        min_dist = distances.min()
        assert min_dist < 0.1, f"Distance to centerline: {min_dist}"

    def test_yaw_offset_range(self, sampler: "InitialStateSampler") -> None:
        """Test that yaw offset is within range."""
        rng = np.random.default_rng(42)
        yaw_offset_range = (-0.5, 0.5)
        states = [
            sampler.sample_initial_state(
                rng=rng,
                lateral_offset_range=(0.0, 0.0),
                yaw_offset_range=yaw_offset_range,
                velocity_range=(10.0, 10.0),
                max_retries=10,
            )
            for _ in range(10)
        ]

        # Get base yaws for each sampled position
        for state in states:
            # Find closest centerline point
            distances = np.sqrt(
                (sampler.track_data["x"] - state["x"]) ** 2
                + (sampler.track_data["y"] - state["y"]) ** 2
            )
            closest_idx = distances.argmin()
            base_yaw = sampler.track_data.iloc[closest_idx]["yaw"]

            # Check yaw difference is within range
            yaw_diff = state["yaw"] - base_yaw
            # Normalize to [-pi, pi]
            yaw_diff = (yaw_diff + np.pi) % (2 * np.pi) - np.pi
            assert yaw_offset_range[0] - 0.01 <= yaw_diff <= yaw_offset_range[1] + 0.01, (
                f"Yaw offset {yaw_diff} outside range {yaw_offset_range}"
            )
