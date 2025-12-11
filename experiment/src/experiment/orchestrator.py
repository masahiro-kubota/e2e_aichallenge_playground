from pathlib import Path
from typing import Any

from experiment.interfaces import Experiment, ExperimentPostprocessor, ExperimentRunner
from experiment.postprocessing.evaluation_postprocessor import EvaluationPostprocessor
from experiment.preprocessing.loader import DefaultPreprocessor
from experiment.runner.runner_factory import DefaultRunnerFactory


class ExperimentOrchestrator:
    """実験全体のオーケストレーター

    - Preprocessorは具体的な実装を直接持つ（動的に変わらない）
    - RunnerとPostprocessorはFactoryで動的生成（実験タイプに応じて変わる）
    """

    def __init__(self) -> None:
        # Preprocessorは具体的な実装を直接組み込み
        self.preprocessor = DefaultPreprocessor()

        # RunnerとPostprocessorはFactoryで動的生成
        # TODO: RunnerもFactoryをやめて直接生成にするか検討
        self.runner_factory = DefaultRunnerFactory()

    def run(self, config_path: Path) -> Any:
        """実験を実行

        1. 前処理: 設定読み込み、コンポーネント生成（固定）
        2. 実行: 設定から実験タイプを判定してRunnerを生成・実行（動的）
        3. 後処理: 実験タイプに応じたPostprocessorを生成・実行(動的)
        """
        # 1. 前処理(実験の生成)
        # Preprocessorが単一の実験インスタンスを生成
        experiment: Experiment = self.preprocessor.create_experiment(config_path)

        # 2. 実験タイプに応じたPostprocessorを動的生成 (Fail Fastのために実行前に生成)
        if experiment.type == "evaluation":
            postprocessor: ExperimentPostprocessor = EvaluationPostprocessor(experiment.config)
        else:
            raise ValueError(f"Unknown experiment type: {experiment.type}")

        # 3. 実験タイプに応じたRunnerを動的生成
        runner: ExperimentRunner = self.runner_factory.create(experiment.type)

        # 4. 実行
        result = runner.run(experiment)

        # 5. 後処理
        processed_result = postprocessor.process(result, experiment.config)

        return processed_result
