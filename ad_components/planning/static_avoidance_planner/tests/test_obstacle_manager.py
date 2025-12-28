import pytest
from core.data.ad_components import Trajectory, TrajectoryPoint, VehicleState
from core.data.environment.obstacle import Obstacle, ObstacleType
from static_avoidance_planner.frenet_converter import FrenetConverter
from static_avoidance_planner.obstacle_manager import ObstacleManager


def create_straight_path(length=100.0):
    points = []
    for x in range(int(length) + 1):
        points.append(TrajectoryPoint(x=float(x), y=0.0, yaw=0.0, velocity=10.0))
    return Trajectory(points=points)


@pytest.fixture
def manager():
    path = create_straight_path()
    converter = FrenetConverter(path)
    return ObstacleManager(converter, lookahead_distance=20.0, road_width=6.0)


def test_filter_valid_obstacle(manager):
    ego = VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=0.0)

    # Obstacle at x=10, y=1 (Ahead, inside road)
    obs = Obstacle(id="1", type=ObstacleType.STATIC, x=10.0, y=1.0, width=1.0, height=2.0)

    targets = manager.get_target_obstacles(ego, [obs])
    assert len(targets) == 1
    assert targets[0].s == pytest.approx(10.0)
    assert targets[0].l == pytest.approx(1.0)
    assert targets[0].width == 1.0
    assert targets[0].length == 2.0


def test_filter_too_far(manager):
    ego = VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=0.0)

    # Obstacle at x=25 (Lookahead is 20)
    obs = Obstacle(id="1", type=ObstacleType.STATIC, x=25.0, y=0.0, width=1.0, height=1.0)

    targets = manager.get_target_obstacles(ego, [obs])
    assert len(targets) == 0


def test_filter_behind(manager):
    ego = VehicleState(x=5.0, y=0.0, yaw=0.0, velocity=0.0)

    # Obstacle at x=2
    obs = Obstacle(id="1", type=ObstacleType.STATIC, x=2.0, y=0.0, width=1.0, height=1.0)

    targets = manager.get_target_obstacles(ego, [obs])
    assert len(targets) == 0


def test_filter_outside_road(manager):
    ego = VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=0.0)

    # Obstacle at y=3.5 (Road width 6.0, half=3.0)
    obs = Obstacle(id="1", type=ObstacleType.STATIC, x=10.0, y=3.5, width=1.0, height=1.0)

    targets = manager.get_target_obstacles(ego, [obs])
    assert len(targets) == 0

    # Exactly on boundary (handle as you wish, usually strictly inside or include? <= vs <)
    # Code says abs(l) >= road_width / 2.0 -> exclude.
    obs2 = Obstacle(id="2", type=ObstacleType.STATIC, x=10.0, y=3.0, width=1.0, height=1.0)
    targets = manager.get_target_obstacles(ego, [obs2])
    assert len(targets) == 0


def test_sort_order(manager):
    ego = VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=0.0)

    obs1 = Obstacle(id="1", type=ObstacleType.STATIC, x=15.0, y=0.0, width=1.0, height=1.0)
    obs2 = Obstacle(id="2", type=ObstacleType.STATIC, x=5.0, y=0.0, width=1.0, height=1.0)

    targets = manager.get_target_obstacles(ego, [obs1, obs2])
    assert len(targets) == 2
    assert targets[0].id == "2"  # Closer one first
    assert targets[1].id == "1"
