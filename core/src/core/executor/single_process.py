"""Single process executor for simulation."""

from typing import TYPE_CHECKING

from core.data import SimulationResult
from core.interfaces.clock import Clock
from core.interfaces.node import Node, SimulationContext
from core.nodes import PhysicsNode

if TYPE_CHECKING:
    pass


class SingleProcessExecutor:
    """Time-based scheduler for single process execution.

    シングルプロセスでシミュレーションを実行するためのスケジューラクラスです。
    シミュレーション時間に基づき、登録された各ノードの実行タイミングを管理します。
    """

    def __init__(self, nodes: list[Node], context: SimulationContext, clock: Clock):
        self.nodes = nodes
        self.context = context
        self.clock = clock

    def run(self, duration: float) -> SimulationResult:
        """Run the simulation loop.

        シミュレーションループを実行します。
        指定された期間(duration)だけループを回し、各ステップで実行すべきノードを呼び出します。
        """
        step_count = 0

        # Get simulator from PhysicsNode for final log retrieval
        # 最終的なログ取得のためにPhysicsNodeからシミュレーターを取得します
        # PhysicsNodeは必須です
        physics_node = next((n for n in self.nodes if isinstance(n, PhysicsNode)), None)
        assert physics_node is not None, "PhysicsNode required"
        simulator = physics_node.simulator

        # Reset simulator if not already done?
        # Expectation: caller calls simulator.reset() and initializes context.
        # 注意: 呼び出し元でsimulator.reset()とcontextの初期化が完了していることを前提としています

        # メインループ: 指定時間経過するか、完了フラグが立つまで継続
        while self.clock.now < duration and not self.context.done:
            self.context.current_time = self.clock.now

            for node in self.nodes:
                # 各ノードに対して、現在の時刻で実行すべきか(周期が来ているか)を確認
                if node.should_run(self.clock.now):
                    node.on_run(self.context)
                    node.next_time += node.period

            self.clock.tick()
            step_count += 1

        return SimulationResult(
            success=self.context.success,
            reason=self.context.done_reason,
            final_state=self.context.sim_state,
            log=simulator.get_log(),
        )
