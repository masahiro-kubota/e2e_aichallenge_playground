"""Training script for Tiny LiDAR Net with Hydra and WandB."""

import logging
from pathlib import Path

import hydra
import torch
import torch.optim as optim
from lib.data import ScanControlDataset
from lib.loss import WeightedSmoothL1Loss
from lib.model import TinyLidarNet
from omegaconf import DictConfig, OmegaConf
from torch.utils.data import DataLoader
from tqdm import tqdm

import wandb

logger = logging.getLogger(__name__)


def train_epoch(model, train_loader, criterion, optimizer, device):
    """Train for one epoch."""
    model.train()
    total_loss = 0.0

    for scans, targets in tqdm(train_loader, desc="Training", leave=False):
        # Add channel dimension: (batch, length) -> (batch, 1, length)
        scans = scans.unsqueeze(1).to(device)
        targets = targets.to(device)

        # Forward pass
        optimizer.zero_grad()
        outputs = model(scans)
        loss = criterion(outputs, targets)

        # Backward pass
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    return total_loss / len(train_loader)


def validate(model, val_loader, criterion, device):
    """Validate the model."""
    model.eval()
    total_loss = 0.0

    with torch.no_grad():
        for scans, targets in tqdm(val_loader, desc="Validation", leave=False):
            scans = scans.unsqueeze(1).to(device)
            targets = targets.to(device)

            outputs = model(scans)
            loss = criterion(outputs, targets)

            total_loss += loss.item()

    return total_loss / len(val_loader)


@hydra.main(version_base=None, config_path="../experiment/conf", config_name="train_tinylidar")
def main(cfg: DictConfig) -> None:
    """Main training entry point."""
    print(OmegaConf.to_yaml(cfg))

    # Initialize WandB
    # We can pass the whole resolved config to wandb
    wandb.init(
        project="e2e-playground",
        name=f"{cfg.experiment.name}_{Path(hydra.core.hydra_config.HydraConfig.get().run.dir).name}",
        config=OmegaConf.to_container(cfg, resolve=True),
        mode="online",  # Force online mode to show dashboard link automatically
    )

    # Get paths from arguments or config
    # We expect dataset data to be passed via command line overrides or config
    # e.g. +train_data=outputs/.../train +val_data=outputs/.../val

    if "train_data" not in cfg or "val_data" not in cfg:
        logger.error("Please provide +train_data and +val_data paths")
        return

    train_dir = Path(cfg.train_data)
    val_dir = Path(cfg.val_data)

    # Training parameters
    params = cfg.training
    model_params = cfg.model

    # Setup device
    device_name = params.get("device", "cpu")
    if device_name == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA not available, falling back to CPU")
        device_name = "cpu"
    device = torch.device(device_name)
    logger.info(f"Using device: {device}")

    # Create datasets
    # Assuming ScanControlDataset is available in lib.data
    # We need to import it. It was imported at top.

    # Note: ScanControlDataset expects specific file structure (scans.npy, etc)
    # Check if files exist
    if not (train_dir / "scans.npy").exists():
        logger.error(f"Training data not found in {train_dir}")
        return

    # Assuming max_range is constant or from config
    max_range = 30.0  # TODO: Make configurable

    train_dataset = ScanControlDataset(train_dir, max_range=max_range)
    val_dataset = ScanControlDataset(val_dir, max_range=max_range)

    # Create data loaders
    train_loader = DataLoader(
        train_dataset, batch_size=params.batch_size, shuffle=True, num_workers=4, pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=params.batch_size, shuffle=False, num_workers=4, pin_memory=True
    )

    # Create model
    # We use the TinyLidarNet from lib.model
    # Note: The input_width in config is 1080.
    model = TinyLidarNet(
        input_dim=model_params.input_width,
        output_dim=2,  # Steering, Acceleration
    ).to(device)

    # Watch model with WandB
    wandb.watch(model, log="all")

    # Create loss and optimizer
    # Weights for loss could be configurable
    criterion = WeightedSmoothL1Loss(accel_weight=1.0, steer_weight=1.0)
    optimizer = optim.Adam(model.parameters(), lr=params.learning_rate)

    # Checkpoints
    checkpoint_dir = Path(hydra.core.hydra_config.HydraConfig.get().run.dir) / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # Training loop
    best_val_loss = float("inf")

    for epoch in range(params.num_epochs):
        train_loss = train_epoch(model, train_loader, criterion, optimizer, device)
        val_loss = validate(model, val_loader, criterion, device)

        # Log metrics
        wandb.log(
            {
                "epoch": epoch + 1,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "best_val_loss": min(best_val_loss, val_loss),
            }
        )

        logger.info(f"Epoch {epoch+1}: Train={train_loss:.4f}, Val={val_loss:.4f}")

        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), checkpoint_dir / "best_model.pth")

            # Save to wandb
            # wandb.save(str(checkpoint_dir / "best_model.pth"))

    logger.info(f"Training completed. Best Val Loss: {best_val_loss}")
    wandb.finish()


if __name__ == "__main__":
    main()
