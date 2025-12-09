"""実験実行の実装モジュール。"""

from typing import TYPE_CHECKING, Any

from core.clock import create_clock
from core.data import SimulationResult
from core.data.frame_data import collect_node_output_fields, create_frame_data_type
from core.executor import SingleProcessExecutor
from core.nodes import PhysicsNode
from experiment_runner.interfaces import ExperimentRunner
from experiment_runner.preprocessing.schemas import ResolvedExperimentConfig

if TYPE_CHECKING:
    pass


class EvaluationRunner(ExperimentRunner[ResolvedExperimentConfig, SimulationResult]):
    """評価実験用のランナー。"""

    def run(self, config: ResolvedExperimentConfig, components: dict[str, Any]) -> SimulationResult:
        """評価実験を実行します。

        Args:
            config: 実験設定
            components: インスタンス化されたコンポーネント (simulator, ad_componentなど)

        Returns:
            Simulation result
        """
        simulator = components["simulator"]
        ad_component = components["ad_component"]

        # 実験パラメータの取得
        max_steps = config.execution.max_steps_per_episode if config.execution else 2000
        sim_rate = config.simulator.rate_hz

        # シミュレータのリセットと初期状態の取得
        _ = simulator.reset()

        # ノードの収集
        nodes = []
        # 1. 物理ノード (PhysicsNode)
        nodes.append(PhysicsNode(simulator, config))

        # 2. ADコンポーネントノード  # noqa: RUF003
        nodes.extend(ad_component.get_schedulable_nodes())

        # FrameDataの構築
        # 1. 全ノードのIO要件を収集  # noqa: RUF003
        fields = collect_node_output_fields(nodes)

        # 2. 動的なFrameDataクラスを作成
        DynamicFrameData = create_frame_data_type(fields)  # noqa: N806

        # 3. Context(FrameData)のインスタンス化
        # 初期値はNoneで初期化され、最初のステップで各ノードがデータを埋めることを想定
        frame_data = DynamicFrameData()

        # コンテキストを各ノードに注入
        for node in nodes:
            node.set_frame_data(frame_data)

        # クロックの作成
        clock_type = config.execution.clock_type if config.execution else "stepped"
        clock = create_clock(start_time=0.0, rate_hz=sim_rate, clock_type=clock_type)

        # Executorの作成
        executor = SingleProcessExecutor(nodes, clock)

        # 実験の実行
        duration = max_steps * (1.0 / sim_rate)
        executor.run(duration=duration, stop_condition=lambda: frame_data.done)

        return SimulationResult(
            success=frame_data.success,
            reason=frame_data.done_reason,
            final_state=frame_data.sim_state,
            log=simulator.get_log(),
        )

    def get_type(self) -> str:
        return "evaluation"
