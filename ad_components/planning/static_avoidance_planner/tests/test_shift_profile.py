import numpy as np
import pytest
from static_avoidance_planner.obstacle_manager import TargetObstacle
from static_avoidance_planner.shift_profile import ShiftProfile, merge_profiles


@pytest.fixture
def left_obs():
    # Obstacle at s=10, l=1.0 (Left). Width=1, Length=2.
    return TargetObstacle(id="1", s=10.0, lat=1.0, length=2.0, width=1.0)


@pytest.fixture
def right_obs():
    # Obstacle at s=10, l=-1.0 (Right). Width=1, Length=2.
    return TargetObstacle(id="2", s=10.0, lat=-1.0, length=2.0, width=1.0)


def test_direction(left_obs, right_obs):
    # Left obs -> Avoid Right (negative l)
    p_left = ShiftProfile(left_obs, vehicle_width=2.0)
    assert p_left.sign < 0
    assert p_left.target_lat < left_obs.lat  # Should be smaller (more negative)

    # Right obs -> Avoid Left (positive l)
    p_right = ShiftProfile(right_obs, vehicle_width=2.0)
    assert p_right.sign > 0
    assert p_right.target_lat > right_obs.lat


def test_profile_shape(left_obs):
    # s range: 10 - 2 - 10 = -2 (start)
    # full avoid: 10 - 2 = 8
    # keep avoid: 10 + 2 + 2 = 14
    # end: 14 + 10 = 24

    p = ShiftProfile(left_obs, vehicle_width=2.0, avoid_distance=10.0, d_front=2.0, d_rear=2.0)

    # Before start
    assert p.get_lat(-5.0) == 0.0

    # At start
    assert p.get_lat(-2.0) == pytest.approx(0.0, abs=1e-3)

    # Mid ramp
    mid = (-2.0 + 8.0) / 2.0
    val = p.get_lat(mid)
    assert abs(val) > 0
    assert abs(val) < abs(p.target_lat)

    # Full avoid
    assert p.get_lat(9.0) == pytest.approx(p.target_lat)

    # End
    assert p.get_lat(25.0) == 0.0


def test_merge_same_side():
    # Two obstacles on left.
    # Obs1: l=1. Target l ~ -1
    # Obs2: l=2. Target l ~ 0 (Wait, if obs is further left, we need less shift to right? No.)
    # If Obs1 at l=1. Safe right boundary < 1 - Clear.
    # If Obs2 at l=2. Safe right boundary < 2 - Clear.
    # So Obs1 is more restrictive (closer to center).

    obs1 = TargetObstacle(id="1", s=10.0, lat=1.0, length=2.0, width=1.0)
    obs2 = TargetObstacle(id="2", s=10.0, lat=2.0, length=2.0, width=1.0)

    p1 = ShiftProfile(obs1, vehicle_width=2.0)  # Avoid Right
    p2 = ShiftProfile(obs2, vehicle_width=2.0)  # Avoid Right

    # p1 target_l will be approx 1 - (0.5 + 1.0 + 0.5) = -1.0
    # p2 target_l will be approx 2 - 2.0 = 0.0
    # So p1 requires l < -1. p2 requires l < 0.
    # Combined requires l < -1. So max shift.

    # Check manual calc
    # Clear = 0.5 + 1.0 + 0.5 = 2.0
    # p1 target = 1.0 - 2.0 = -1.0
    # p2 target = 2.0 - 2.0 = 0.0

    s = np.array([10.0])
    l_tgt, coll = merge_profiles(s, [p1, p2])

    assert not coll
    assert l_tgt[0] == pytest.approx(-1.0)  # More negative one


def test_merge_slalom():
    # Obs1 Left (l=2) -> Req l < 0
    # Obs2 Right (l=-2) -> Req l > 0

    obs1 = TargetObstacle(id="1", s=10.0, lat=2.0, length=2.0, width=1.0)
    obs2 = TargetObstacle(id="2", s=10.0, lat=-2.0, length=2.0, width=1.0)

    p1 = ShiftProfile(obs1, vehicle_width=2.0)  # Target l = 0 (Left req < 0)
    p2 = ShiftProfile(obs2, vehicle_width=2.0)  # Target l = 0 (Right req > 0)

    # Both active at s=10
    s = np.array([10.0])
    l_tgt, coll = merge_profiles(s, [p1, p2])

    assert not coll
    assert l_tgt[0] == pytest.approx(0.0)


def test_merge_collision():
    # Obs1 Left (l=1) -> Req l < -1
    # Obs2 Right (l=-1) -> Req l > 1
    # Impossible interval: 1 < l < -1 -> Empty set.

    obs1 = TargetObstacle(id="1", s=10.0, lat=1.0, length=2.0, width=1.0)
    obs2 = TargetObstacle(id="2", s=10.0, lat=-1.0, length=2.0, width=1.0)

    p1 = ShiftProfile(obs1, vehicle_width=2.0)
    p2 = ShiftProfile(obs2, vehicle_width=2.0)

    s = np.array([10.0])
    _, coll = merge_profiles(s, [p1, p2])

    assert coll
