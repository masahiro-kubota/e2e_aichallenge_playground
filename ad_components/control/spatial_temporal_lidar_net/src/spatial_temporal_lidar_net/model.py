import torch
import torch.nn as nn
import torch.nn.functional as F

class SpatialTemporalLidarNet(nn.Module):
    def __init__(self, input_dim=1080, num_frames=20, output_dim=1):
        super(SpatialTemporalLidarNet, self).__init__()
        
        # Input shape: (Batch, 1, Frames, Beams) -> (B, 1, 20, 1080)
        
        # Conv1
        # Strides: (1, 2) -> Reduce Beam dimension faster, keep Temporal dimension more detailed initially?
        # Or reduce both. Let's try to preserve Temporal a bit.
        self.conv1 = nn.Conv2d(in_channels=1, out_channels=16, kernel_size=(3, 5), stride=(1, 2), padding=(1, 2))
        self.bn1 = nn.BatchNorm2d(16)
        
        # Conv2
        self.conv2 = nn.Conv2d(in_channels=16, out_channels=32, kernel_size=(3, 3), stride=(2, 2), padding=(1, 1))
        self.bn2 = nn.BatchNorm2d(32)
        
        # Conv3
        self.conv3 = nn.Conv2d(in_channels=32, out_channels=64, kernel_size=(3, 3), stride=(2, 2), padding=(1, 1))
        self.bn3 = nn.BatchNorm2d(64)
        
        # Calculate flatten size
        # H_in = 20, W_in = 1080
        # Conv1: H=20, W=540 (stride 1, 2)
        # Conv2: H=10, W=270 (stride 2, 2)
        # Conv3: H=5, W=135 (stride 2, 2)
        # 64 * 5 * 135 = 43200 -> slightly large.
        
        # Let's add Conv4
        self.conv4 = nn.Conv2d(in_channels=64, out_channels=128, kernel_size=(3, 3), stride=(2, 2), padding=(1, 1))
        self.bn4 = nn.BatchNorm2d(128)
        # Conv4: H=3, W=68 (stride 2, 2)
        
        self.flatten_size = 128 * 3 * 68
        
        self.fc1 = nn.Linear(self.flatten_size, 256)
        self.fc2 = nn.Linear(256, 64)
        self.fc3 = nn.Linear(64, output_dim)
        
    def forward(self, x):
        # x: (B, 1, T, W)
        
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = F.relu(self.bn4(self.conv4(x)))
        
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        
        return x
