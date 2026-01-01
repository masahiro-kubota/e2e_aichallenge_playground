import argparse
import sys
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from pathlib import Path
import matplotlib.pyplot as plt
import logging

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from spatial_temporal_lidar_net.model import SpatialTemporalLidarNet
from spatial_temporal_lidar_net.dataset import StackedScanDataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def train(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    
    # Dataset & Loader
    train_dataset = StackedScanDataset(args.train_dir, num_frames=args.num_frames)
    val_dataset = StackedScanDataset(args.val_dir, num_frames=args.num_frames)
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=4)
    
    logger.info(f"Train samples: {len(train_dataset)}, Val samples: {len(val_dataset)}")
    
    # Model
    model = SpatialTemporalLidarNet(num_frames=args.num_frames).to(device)
    
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    
    best_val_loss = float('inf')
    early_stop_counter = 0
    
    train_losses = []
    val_losses = []
    
    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    for epoch in range(args.epochs):
        # Train
        model.train()
        total_train_loss = 0.0
        for imgs, steers in train_loader:
            imgs, steers = imgs.to(device), steers.to(device)
            
            optimizer.zero_grad()
            outputs = model(imgs)
            loss = criterion(outputs, steers)
            loss.backward()
            optimizer.step()
            
            total_train_loss += loss.item()
            
        avg_train_loss = total_train_loss / len(train_loader)
        train_losses.append(avg_train_loss)
        
        # Val
        model.eval()
        total_val_loss = 0.0
        with torch.no_grad():
            for imgs, steers in val_loader:
                imgs, steers = imgs.to(device), steers.to(device)
                outputs = model(imgs)
                loss = criterion(outputs, steers)
                total_val_loss += loss.item()
                
        avg_val_loss = total_val_loss / len(val_loader)
        val_losses.append(avg_val_loss)
        
        logger.info(f"Epoch {epoch+1}/{args.epochs} - Train Loss: {avg_train_loss:.6f}, Val Loss: {avg_val_loss:.6f}")
        
        # Checkpoint
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            early_stop_counter = 0
            torch.save(model.state_dict(), checkpoint_dir / "best_model.pth")
            logger.info("Saved best model.")
        else:
            early_stop_counter += 1
            if early_stop_counter >= args.early_stop_patience:
                logger.info("Early stopping triggered.")
                break
                
    # Plot
    plt.figure()
    plt.plot(train_losses, label='Train Loss')
    plt.plot(val_losses, label='Val Loss')
    plt.xlabel('Epoch')
    plt.ylabel('MSE Loss')
    plt.legend()
    plt.savefig(checkpoint_dir / "loss_curve.png")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-dir", required=True, type=str)
    parser.add_argument("--val-dir", required=True, type=str)
    parser.add_argument("--checkpoint-dir", default="checkpoints", type=str)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--num-frames", type=int, default=20)
    parser.add_argument("--early-stop-patience", type=int, default=10)
    
    args = parser.parse_args()
    train(args)
