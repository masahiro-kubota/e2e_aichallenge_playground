import json
import logging
from pathlib import Path
from typing import Any

import torch
import torch.optim as optim
from omegaconf import DictConfig, OmegaConf
from torch.utils.data import DataLoader

import wandb
from experiment.data.dataset import ScanControlDataset
from experiment.engine.base import BaseEngine
from experiment.engine.loss import WeightedSmoothL1Loss
from experiment.models.tiny_lidar import TinyLidarNet

logger = logging.getLogger(__name__)


class TrainerEngine(BaseEngine):
    """学習エンジン"""

    def run(self, cfg: DictConfig) -> Any:
        # WandB初期化
        wandb.init(
            project="e2e-playground",
            config=OmegaConf.to_container(cfg, resolve=True),
        )

        train_dir = Path(cfg.train_data)
        val_dir = Path(cfg.val_data)

        # 統計量のロード (もしあれば)
        stats = None
        stats_path = train_dir / "stats.json"
        if stats_path.exists():
            with open(stats_path) as f:
                stats = json.load(f)
            logger.info(f"Loaded statistics from {stats_path}")

        train_dataset = ScanControlDataset(train_dir, stats=stats)
        val_dataset = ScanControlDataset(val_dir, stats=stats)

        # ExtractorEngine (旧 ad_components の抽出ロジックを統合) によって
        # 計算された統計量を適用して学習を行います。

        _train_loader = DataLoader(train_dataset, batch_size=cfg.training.batch_size, shuffle=True)
        _val_loader = DataLoader(val_dataset, batch_size=cfg.training.batch_size)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = TinyLidarNet(input_dim=cfg.model.input_width, output_dim=2).to(device)

        _optimizer = optim.Adam(model.parameters(), lr=cfg.training.learning_rate)
        _criterion = WeightedSmoothL1Loss()

        for epoch in range(cfg.training.num_epochs):
            # Training/Validation loop...
            pass

        wandb.finish()
        return "Training Completed"
