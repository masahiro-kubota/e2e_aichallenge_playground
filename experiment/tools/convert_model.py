"""Convert PyTorch checkpoint to NumPy format."""

import argparse
from pathlib import Path

import numpy as np
import torch

from experiment.models.tiny_lidar import TinyLidarNet


def convert_pytorch_to_numpy(ckpt_path: Path, output_path: Path):
    """Convert PyTorch checkpoint to NumPy format.

    Args:
        ckpt_path: Path to PyTorch checkpoint (.pth)
        output_path: Path to save NumPy weights (.npy)
    """
    # Load PyTorch model
    # Note: TinyLidarNet currently has input_dim, output_dim params
    model = TinyLidarNet(input_dim=1080, output_dim=2)

    # Load state dict
    state_dict = torch.load(ckpt_path, map_location="cpu")
    model.load_state_dict(state_dict)

    # Extract weights as NumPy arrays
    numpy_weights = {}

    for name, param in model.named_parameters():
        # Convert parameter name format: conv1.weight -> conv1_weight
        numpy_name = name.replace(".", "_")
        numpy_weights[numpy_name] = param.detach().cpu().numpy()

    # Save as NumPy file
    np.save(output_path, numpy_weights)

    print(f"Converted {len(numpy_weights)} parameters")
    print(f"Saved to: {output_path}")
    print("\nParameter names:")
    for name in sorted(numpy_weights.keys()):
        print(f"  {name}: {numpy_weights[name].shape}")


def main():
    parser = argparse.ArgumentParser(description="Convert PyTorch checkpoint to NumPy")
    parser.add_argument("--ckpt", type=Path, required=True, help="Path to PyTorch checkpoint")
    parser.add_argument("--output", type=Path, required=True, help="Path to save NumPy weights")

    args = parser.parse_args()

    convert_pytorch_to_numpy(args.ckpt, args.output)


if __name__ == "__main__":
    main()
