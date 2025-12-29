"""Loss functions for Tiny LiDAR Net training."""

import torch
import torch.nn as nn


class SteeringLoss(nn.Module):
    """Smooth L1 loss for steering angle prediction.

    This is a simple wrapper around PyTorch's SmoothL1Loss for consistency
    with the previous API, but now optimized for single-output (steering only) models.
    """

    def __init__(self):
        """Initialize the SteeringLoss."""
        super().__init__()
        self.criterion = nn.SmoothL1Loss()

    def forward(self, outputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Calculate the steering loss.

        Args:
            outputs: Model predictions. Shape: (Batch_Size,) or (Batch_Size, 1)
            targets: Ground truth steering values. Shape: (Batch_Size,) or (Batch_Size, 1)

        Returns:
            Scalar tensor representing the loss
        """
        return self.criterion(outputs.squeeze(), targets.squeeze())
