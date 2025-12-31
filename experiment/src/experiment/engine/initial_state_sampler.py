"""Initial state sampling for data collection.

This module provides functionality to sample random initial states
from a centerline track, with Lanelet validation.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from simulator.map import LaneletMap

logger = logging.getLogger(__name__)


class InitialStateSampler:
    """Sample random initial states from centerline track."""

    def __init__(self, track_path: Path, map_instance: "LaneletMap") -> None:
        """Initialize sampler.

        Args:
            track_path: Path to centerline CSV file
            map_instance: LaneletMap instance for drivable area checking
        """
        self.map_instance = map_instance
        self.track_data = self._load_track(track_path)

    def _load_track(self, track_path: Path) -> pd.DataFrame:
        """Load centerline track data.

        Args:
            track_path: Path to CSV file (x,y,z,x_quat,y_quat,z_quat,w_quat,speed)

        Returns:
            DataFrame with columns: x, y, yaw
        """
        df = pd.read_csv(track_path)

        # Convert quaternion to yaw
        # For 2D rotation: yaw = atan2(2*(w*z + x*y), 1 - 2*(y^2 + z^2))
        x_quat = df["x_quat"].values
        y_quat = df["y_quat"].values
        z_quat = df["z_quat"].values
        w_quat = df["w_quat"].values

        yaw = np.arctan2(
            2.0 * (w_quat * z_quat + x_quat * y_quat),
            1.0 - 2.0 * (y_quat**2 + z_quat**2),
        )

        track_df = pd.DataFrame({"x": df["x"], "y": df["y"], "yaw": yaw})

        logger.info(f"Loaded centerline with {len(track_df)} points")
        return track_df

    def sample_initial_state(
        self,
        rng: np.random.Generator,
        lateral_offset_range: tuple[float, float],
        yaw_offset_range: tuple[float, float],
        velocity_range: tuple[float, float],
        max_retries: int = 10,
    ) -> dict[str, float]:
        """Sample a random initial state from centerline.

        Args:
            rng: Random number generator
            lateral_offset_range: Range for lateral offset from centerline [m]
            yaw_offset_range: Range for yaw offset from centerline direction [rad]
            velocity_range: Range for initial velocity [m/s]
            max_retries: Maximum number of retries for Lanelet validation

        Returns:
            Dictionary with keys: x, y, yaw, velocity

        Raises:
            RuntimeError: If failed to find valid position within max_retries
        """
        for attempt in range(max_retries):
            # 1. Sample random point on centerline
            idx = rng.integers(0, len(self.track_data))
            base_x = self.track_data.iloc[idx]["x"]
            base_y = self.track_data.iloc[idx]["y"]
            base_yaw = self.track_data.iloc[idx]["yaw"]

            # 2. Sample lateral offset
            lateral_offset = rng.uniform(lateral_offset_range[0], lateral_offset_range[1])

            # 3. Apply lateral offset perpendicular to centerline direction
            # Perpendicular direction is (base_yaw + pi/2)
            perp_yaw = base_yaw + np.pi / 2.0
            final_x = base_x + lateral_offset * np.cos(perp_yaw)
            final_y = base_y + lateral_offset * np.sin(perp_yaw)

            # 4. Check if position is within drivable area
            if not self.map_instance.is_drivable(final_x, final_y):
                logger.debug(
                    f"Attempt {attempt + 1}/{max_retries}: "
                    f"Position ({final_x:.2f}, {final_y:.2f}) is not drivable, retrying..."
                )
                continue

            # 5. Sample yaw and velocity
            yaw_offset = rng.uniform(yaw_offset_range[0], yaw_offset_range[1])
            final_yaw = base_yaw + yaw_offset
            final_velocity = rng.uniform(velocity_range[0], velocity_range[1])

            logger.info(
                f"Sampled initial state: x={final_x:.2f}, y={final_y:.2f}, "
                f"yaw={final_yaw:.3f}, velocity={final_velocity:.2f} "
                f"(attempt {attempt + 1})"
            )

            return {
                "x": float(final_x),
                "y": float(final_y),
                "yaw": float(final_yaw),
                "velocity": float(final_velocity),
            }

        # Failed to find valid position
        msg = f"Failed to sample valid initial state within {max_retries} retries"
        raise RuntimeError(msg)
