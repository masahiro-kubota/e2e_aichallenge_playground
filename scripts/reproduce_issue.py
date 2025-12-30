
import sys
import os
import numpy as np
from dataclasses import dataclass

# Add correct paths
base_dir = "/home/masa/python-self-driving-simulator"
sys.path.append(os.path.join(base_dir, "core/src"))
sys.path.append(os.path.join(base_dir, "ad_components/planning/lateral_shift_planner/src"))
sys.path.append(os.path.join(base_dir, "ad_components/planning/planning_utils/src"))

# Mock TargetObstacle
@dataclass
class TargetObstacle:
    id: str
    s: float
    lat: float
    length: float
    width: float
    left_boundary_dist: float
    right_boundary_dist: float
    raw: any = None

try:
    from lateral_shift_planner.shift_profile import ShiftProfile, merge_profiles
except ImportError as e:
    print(f"Import failed: {e}")
    # print sys.path to debug
    print("sys.path:")
    for p in sys.path:
        print(p)
    sys.exit(1)

def test_overlap_collision():
    print("Testing overlap collision...")
    
    # Obstacle 1: Requires RIGHT shift
    obs1 = TargetObstacle(
        id="1", s=10.0, lat=0.0, length=2.0, width=2.0,
        left_boundary_dist=1.0, right_boundary_dist=5.0 
    )
    
    # Obstacle 2: Requires LEFT shift
    obs2 = TargetObstacle(
        id="2", s=20.0, lat=0.0, length=2.0, width=2.0,
        left_boundary_dist=5.0, right_boundary_dist=1.0
    )
    
    # Config
    vehicle_width = 2.0
    safe_margin = 0.5
    maneuver_length = 10.0
    margin_front = 0.0
    margin_rear = 0.0
    
    # Create profiles
    p1 = ShiftProfile(obs1, vehicle_width, safe_margin, maneuver_length, margin_front, margin_rear)
    p2 = ShiftProfile(obs2, vehicle_width, safe_margin, maneuver_length, margin_front, margin_rear)
    
    print(f"Profile 1 (Right): Start={p1.s_start_action}, End={p1.s_end_action}, Target={p1.target_lat:.2f} (Sign={p1.sign})")
    print(f"Profile 2 (Left): Start={p2.s_start_action}, End={p2.s_end_action}, Target={p2.target_lat:.2f} (Sign={p2.sign})")
    
    # Sample s from 0 to 40
    s_samples = np.arange(0.0, 40.0, 1.0)
    
    lat_targets, collision = merge_profiles(s_samples, [p1, p2])
    
    print(f"Collision Detected: {collision}")
    
    # Check at s=30 (should be covered by p2, which is Left shift -> Positive)
    val_at_30 = lat_targets[30]
    print(f"Value at s=30: {val_at_30}")
    
    if collision and val_at_30 == 0.0:
        print("FAIL: Value at s=30 is 0.0 despite active p2. Merge returned early.")
        exit(1)
    elif collision and val_at_30 > 0.0:
        print("SUCCESS: Value at s=30 is non-zero. Merge continued.")
    else:
        print("Unclear result.")
        exit(1)

if __name__ == "__main__":
    test_overlap_collision()
