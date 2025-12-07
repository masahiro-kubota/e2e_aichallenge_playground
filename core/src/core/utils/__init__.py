"""Utility functions and classes."""

from core.utils.config import (
    get_nested_value,
    load_yaml,
    merge_configs,
    save_yaml,
    set_nested_value,
)
from core.utils.geometry import (
    angle_between_points,
    curvature_from_points,
    distance,
    nearest_point_on_line,
    normalize_angle,
    rotate_point,
)
from core.utils.paths import get_project_root
from core.utils.transforms import (
    global_to_local,
    local_to_global,
    rotation_matrix_2d,
    transform_angle_to_global,
    transform_angle_to_local,
    transformation_matrix_2d,
)

__all__ = [
    "angle_between_points",
    "curvature_from_points",
    "distance",
    "get_nested_value",
    "get_project_root",
    "global_to_local",
    "load_yaml",
    "local_to_global",
    "merge_configs",
    "nearest_point_on_line",
    "normalize_angle",
    "rotate_point",
    "rotation_matrix_2d",
    "save_yaml",
    "set_nested_value",
    "transform_angle_to_global",
    "transform_angle_to_local",
    "transformation_matrix_2d",
]
