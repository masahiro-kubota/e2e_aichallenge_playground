"""Tests for ExtractorEngine filtering logic."""

import json
from pathlib import Path

import pytest
from omegaconf import DictConfig, OmegaConf


class TestExcludeFailureReasons:
    """Tests for exclude_failure_reasons filtering in ExtractorEngine."""

    @pytest.fixture
    def setup_test_data(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create test directory with dummy result.json files.

        Creates 4 episodes:
        - episode_0: success
        - episode_1: failed (off_track)
        - episode_2: failed (collision)
        - episode_3: failed (timeout)
        """
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"

        episodes = [
            {"episode_idx": 0, "success": True, "reason": "goal", "metrics": {}},
            {"episode_idx": 1, "success": False, "reason": "off_track", "metrics": {}},
            {"episode_idx": 2, "success": False, "reason": "collision", "metrics": {}},
            {"episode_idx": 3, "success": False, "reason": "timeout", "metrics": {}},
        ]

        for ep in episodes:
            ep_dir = input_dir / f"episode_{ep['episode_idx']}"
            ep_dir.mkdir(parents=True)

            # Create result.json
            with open(ep_dir / "result.json", "w") as f:
                json.dump(ep, f)

            # Create dummy mcap file (empty)
            (ep_dir / "simulation.mcap").touch()

        return input_dir, output_dir

    def _create_config(
        self, input_dir: Path, output_dir: Path, exclude_failure_reasons: list[str] | None = None
    ) -> DictConfig:
        """Create test configuration."""
        cfg_dict = {
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "dvc": {"auto_add": False, "auto_push": False},
            "experiment": {
                "name": "test",
                "type": "extraction",
                "description": "test",
                "topics": {
                    "control": "/control/command/control_cmd",
                    "scan": "/sensing/lidar/scan",
                },
            },
        }
        if exclude_failure_reasons is not None:
            cfg_dict["exclude_failure_reasons"] = exclude_failure_reasons
        return OmegaConf.create(cfg_dict)

    def test_exclude_all_failures_when_null(self, setup_test_data: tuple[Path, Path]) -> None:
        """exclude_failure_reasons=null should exclude all failed episodes."""
        input_dir, output_dir = setup_test_data
        cfg = self._create_config(input_dir, output_dir, exclude_failure_reasons=None)

        from experiment.engine.extractor import ExtractorEngine

        engine = ExtractorEngine()

        # Count how many episodes get processed
        processed_episodes = []

        def mock_extract(mcap_path, _cfg=None):
            processed_episodes.append(mcap_path.parent.name)
            return None  # Skip actual extraction

        engine._extract_from_single_mcap = mock_extract
        engine._run_impl(cfg)

        # Only successful episode should be processed
        assert processed_episodes == ["episode_0"], f"Got: {processed_episodes}"

    def test_include_all_failures_when_empty_list(self, setup_test_data: tuple[Path, Path]) -> None:
        """exclude_failure_reasons=[] should include all episodes."""
        input_dir, output_dir = setup_test_data
        cfg = self._create_config(input_dir, output_dir, exclude_failure_reasons=[])

        from experiment.engine.extractor import ExtractorEngine

        engine = ExtractorEngine()

        processed_episodes = []

        def mock_extract(mcap_path, _cfg=None):
            processed_episodes.append(mcap_path.parent.name)
            return None

        engine._extract_from_single_mcap = mock_extract
        engine._run_impl(cfg)

        # All episodes should be processed
        assert len(processed_episodes) == 4
        assert set(processed_episodes) == {"episode_0", "episode_1", "episode_2", "episode_3"}

    def test_exclude_specific_reason(self, setup_test_data: tuple[Path, Path]) -> None:
        """exclude_failure_reasons=['off_track'] should exclude only off_track failures."""
        input_dir, output_dir = setup_test_data
        cfg = self._create_config(input_dir, output_dir, exclude_failure_reasons=["off_track"])

        from experiment.engine.extractor import ExtractorEngine

        engine = ExtractorEngine()

        processed_episodes = []

        def mock_extract(mcap_path, _cfg=None):
            processed_episodes.append(mcap_path.parent.name)
            return None

        engine._extract_from_single_mcap = mock_extract
        engine._run_impl(cfg)

        # episode_1 (off_track) should be excluded
        assert "episode_1" not in processed_episodes
        # Others should be included
        assert "episode_0" in processed_episodes  # success
        assert "episode_2" in processed_episodes  # collision
        assert "episode_3" in processed_episodes  # timeout

    def test_exclude_multiple_reasons(self, setup_test_data: tuple[Path, Path]) -> None:
        """exclude_failure_reasons=['off_track', 'collision'] should exclude both."""
        input_dir, output_dir = setup_test_data
        cfg = self._create_config(
            input_dir, output_dir, exclude_failure_reasons=["off_track", "collision"]
        )

        from experiment.engine.extractor import ExtractorEngine

        engine = ExtractorEngine()

        processed_episodes = []

        def mock_extract(mcap_path, _cfg=None):
            processed_episodes.append(mcap_path.parent.name)
            return None

        engine._extract_from_single_mcap = mock_extract
        engine._run_impl(cfg)

        # off_track and collision should be excluded
        assert "episode_1" not in processed_episodes
        assert "episode_2" not in processed_episodes
        # success and timeout should be included
        assert "episode_0" in processed_episodes
        assert "episode_3" in processed_episodes
