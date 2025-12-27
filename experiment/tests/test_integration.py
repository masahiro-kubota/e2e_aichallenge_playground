import shutil
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from experiment.core.orchestrator import ExperimentOrchestrator


def run_integration_test(agent_name: str, overrides: list[str] | None = None) -> Any:
    """整合テストを実行し、結果を検証する共通ヘルパー関数"""
    from hydra import compose, initialize_config_dir
    from mcap.reader import make_reader
    from omegaconf import OmegaConf

    workspace_root = Path(__file__).parent.parent.parent
    config_dir = str(workspace_root / "experiment/conf")
    tmp_path = workspace_root / "tmp" / f"test_{agent_name}"
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)

    base_overrides = [
        "experiment=evaluation",
        f"ad_components={agent_name}",
        "execution.duration_sec=200.0",
        "execution.num_episodes=1",
    ]
    if overrides:
        base_overrides.extend(overrides)

    with initialize_config_dir(config_dir=config_dir, version_base=None):
        cfg = compose(config_name="config", overrides=base_overrides)

        # Hydra の実行時変数を手動設定
        OmegaConf.set_struct(cfg, False)
        cfg["hydra"] = {"runtime": {"output_dir": str(tmp_path)}}
        cfg["output_dir"] = str(tmp_path)

        # 各ノードの出力パスを tmp_path に向ける
        if "postprocess" in cfg and "mcap" in cfg.postprocess:
            cfg.postprocess.mcap.output_dir = str(tmp_path)

        nodes_iter = (
            cfg.system.nodes.values() if isinstance(cfg.system.nodes, dict) else cfg.system.nodes
        )
        for node in nodes_iter:
            node_params = (
                node.get("params", {}) if isinstance(node, dict) else getattr(node, "params", {})
            )
            if "output_mcap_path" in node_params:
                if isinstance(node, dict):
                    node["params"]["output_mcap_path"] = str(tmp_path / "simulation.mcap")
                else:
                    node.params.output_mcap_path = str(tmp_path / "simulation.mcap")

        OmegaConf.set_struct(cfg, True)

        # 実験の実行
        orchestrator = ExperimentOrchestrator()
        result = orchestrator.run_from_hydra(cfg)

    # 検証: 結果が存在すること
    assert result is not None
    assert len(result.simulation_results) > 0
    metrics = result.metrics

    # 検証: 成功していること (衝突がないこと)
    assert metrics.collision_count == 0, f"Collision occurred for {agent_name}"

    # 検証: MCAPファイルが生成されていること
    mcap_path = tmp_path / "simulation.mcap"
    mcap_source = tmp_path / "episode_0000" / "simulation.mcap"
    if mcap_source.exists():
        if mcap_path.exists():
            mcap_path.unlink()
        shutil.move(mcap_source, mcap_path)

    assert mcap_path.exists(), f"MCAP file not found for {agent_name}"

    # MCAP の中身を詳しく検証
    with open(mcap_path, "rb") as f:
        reader = make_reader(f)
        summary = reader.get_summary()
        assert summary is not None
        topics = [c.topic for c in summary.channels.values()]
        expected_topics = [
            "/tf",
            "/localization/kinematic_state",
            "/simulation/info",
            "/control/command/control_cmd",
            "/map/vector",
        ]
        for topic in expected_topics:
            assert topic in topics, f"Topic {topic} missing in MCAP for {agent_name}"

    # Dashboard 検証
    assert any(a.local_path.suffix == ".html" for a in result.artifacts), "Dashboard not found"

    return result


@pytest.mark.integration
@patch("experiment.engine.base.mlflow")
@patch("experiment.engine.evaluator.mlflow")
def test_pure_pursuit_integration(_mock_mlflow_eval, _mock_mlflow_base) -> None:
    """Pure Pursuit エージェントの整合テスト"""
    result = run_integration_test("pure_pursuit")
    assert result.simulation_results[0].success
    assert result.metrics.goal_count == 1
    assert result.metrics.checkpoint_count == 3


@pytest.mark.integration
@patch("experiment.engine.base.mlflow")
@patch("experiment.engine.evaluator.mlflow")
def test_mppi_integration(_mock_mlflow_eval, _mock_mlflow_base) -> None:
    """MPPI エージェントの整合テスト"""
    result = run_integration_test("mppi")
    assert result.simulation_results[0].success
    assert result.metrics.goal_count >= 1
    assert result.metrics.checkpoint_count >= 1
