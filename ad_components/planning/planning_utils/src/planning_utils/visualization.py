"""Visualization utilities for planning components."""

from core.data import Trajectory
from core.data.ros import ColorRGBA, Header, Marker, Point, Pose, Quaternion, Time, Vector3


def to_ros_time(timestamp: float) -> Time:
    """Convert float timestamp to ROS Time."""
    sec = int(timestamp)
    nanosec = int((timestamp - sec) * 1e9)
    return Time(sec=sec, nanosec=nanosec)


def create_trajectory_marker(
    trajectory: Trajectory,
    timestamp: float,
    ns: str = "trajectory",
    id: int = 0,
    r: float = 0.0,
    g: float = 1.0,
    b: float = 0.0,
    a: float = 0.8,
) -> Marker:
    """Create a marker for the trajectory or lookahead point.

    Args:
        trajectory: Trajectory data.
        timestamp: Current timestamp.
        ns: Namespace for the marker.
        id: Marker ID.
        r, g, b, a: Color components.

    Returns:
        Marker representing the trajectory.
    """
    ros_time = to_ros_time(timestamp)
    identity_quat = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)

    # If trajectory has only one point, it's likely a lookahead target
    # We visualize it as a Sphere
    if len(trajectory.points) == 1:
        point = trajectory.points[0]
        return Marker(
            header=Header(stamp=ros_time, frame_id="map"),
            ns=ns,
            id=id,
            type=2,  # SPHERE
            action=0,
            pose=Pose(
                position=Point(x=point.x, y=point.y, z=0.5),  # Slightly elevated
                orientation=identity_quat,
            ),
            scale=Vector3(x=0.5, y=0.5, z=0.5),
            color=ColorRGBA(r=1.0, g=0.0, b=1.0, a=0.8),  # Magenta for single point (target)
            frame_locked=True,
        )

    # If multiple points, visualize as Path (Line Strip)
    points = [Point(x=p.x, y=p.y, z=0.2) for p in trajectory.points]
    return Marker(
        header=Header(stamp=ros_time, frame_id="map"),
        ns=ns,
        id=id,
        type=4,  # LINE_STRIP
        action=0,
        pose=Pose(
            position=Point(x=0.0, y=0.0, z=0.0),  # Points are absolute
            orientation=identity_quat,
        ),
        scale=Vector3(x=0.2, y=0.0, z=0.0),  # x is line width
        color=ColorRGBA(r=r, g=g, b=b, a=a),
        points=points,
        frame_locked=True,
    )
