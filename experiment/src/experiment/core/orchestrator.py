from typing import Any

from omegaconf import DictConfig


class ExperimentOrchestrator:
    """実験フェーズのオーケストレーター"""

    def run_from_hydra(self, cfg: DictConfig) -> Any:
        """Hydra設定から実験フェーズを実行"""
        phase = cfg.experiment.type

        if phase == "data_collection":
            from experiment.engine.collector import CollectorEngine

            engine = CollectorEngine()
        elif phase == "extraction":
            from experiment.engine.extractor import ExtractorEngine

            engine = ExtractorEngine()
        elif phase == "training":
            from experiment.engine.trainer import TrainerEngine

            engine = TrainerEngine()
        elif phase == "evaluation":
            from experiment.engine.evaluator import EvaluatorEngine

            engine = EvaluatorEngine()
        else:
            raise ValueError(f"Unknown experiment phase: {phase}")

        return engine.run(cfg)
