from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


class StackedScanDataset(Dataset):
    def __init__(self, data_dir, num_frames=20, normalize=True):
        self.data_dir = Path(data_dir)
        self.num_frames = num_frames
        self.normalize = normalize

        self.scans = np.load(self.data_dir / "scans.npy")
        self.steers = np.load(self.data_dir / "steers.npy")

        # Normalize scans (0-1) assuming max range 30.0
        if self.normalize:
            self.scans = np.clip(self.scans / 30.0, 0.0, 1.0)

        self.num_samples = len(self.scans)

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # Retrieve past K frames
        # Indices: [idx - K + 1, ..., idx]

        indices = np.arange(idx - self.num_frames + 1, idx + 1)

        # Handle negative indices (padding)
        # Verify valid indices mask
        valid_mask = indices >= 0

        # Create buffer
        stacked = np.zeros((self.num_frames, self.scans.shape[1]), dtype=np.float32)

        if np.all(valid_mask):
            stacked = self.scans[indices]
        else:
            # Need padding with the first frame (index 0)
            # Actually, standard padding is usually valid frames or duplicates.
            # Here we duplicate index 0 for negative indices.
            valid_indices = indices[valid_mask]

            # Fill valid parts
            stacked[valid_mask] = self.scans[valid_indices]

            # Fill invalid parts with scan[0]
            if len(valid_indices) > 0:
                # Better: pad with the first VALID frame of this sequence?
                # Or just duplicate the oldest available frame.
                # Simpler: just use scan[0] for global 0.
                stacked[~valid_mask] = self.scans[0]
            else:
                stacked[:] = self.scans[0]

        # Shape: (K, W) -> (1, K, W) for Conv2d
        img = torch.from_numpy(stacked).unsqueeze(0).float()

        # Target: Current steering
        steer = torch.tensor([self.steers[idx]], dtype=torch.float32)

        return img, steer
