"""Tests for system reference resolution in configuration loader."""

import pytest

from core.data import VehicleParameters
from experiment.preprocessing.loader import (
    _build_system_context,
    _resolve_nested_reference,
    _resolve_system_references,
)
from experiment.preprocessing.schemas import SystemConfig

# Dummy vehicle parameters for testing
DUMMY_VEHICLE_PARAMS = {
    "wheelbase": 1.087,
    "width": 1.30,
    "max_steering_angle": 0.64,
    "front_overhang": 0.467,
    "rear_overhang": 0.510,
    "max_velocity": 35.0,
    "max_acceleration": 5.0,
    "mass": 1500.0,
    "inertia": 2500.0,
    "lf": 1.2,
    "lr": 1.3,
    "cf": 80000.0,
    "cr": 80000.0,
    "c_drag": 0.3,
    "c_roll": 0.015,
    "max_drive_force": 5000.0,
    "max_brake_force": 8000.0,
}


def test_resolve_simple_reference():
    """Test resolving a simple ${system.*} reference."""
    system_context = {
        "map_path": "/absolute/path/to/map.osm",
        "vehicle_params": VehicleParameters(**DUMMY_VEHICLE_PARAMS),
    }

    params = {
        "map_path": "${system.map_path}",
        "other_param": "unchanged",
    }

    resolved = _resolve_system_references(params, system_context)

    assert resolved["map_path"] == "/absolute/path/to/map.osm"
    assert resolved["other_param"] == "unchanged"


def test_resolve_nested_reference():
    """Test resolving a nested ${system.vehicle.config_path} reference."""
    system_context = {
        "vehicle": {
            "config_path": "/path/to/vehicle.yaml",
            "params": VehicleParameters(**DUMMY_VEHICLE_PARAMS),
        },
    }

    params = {
        "vehicle_config": "${system.vehicle.config_path}",
    }

    resolved = _resolve_system_references(params, system_context)

    assert resolved["vehicle_config"] == "/path/to/vehicle.yaml"


def test_resolve_reference_in_nested_dict():
    """Test resolving references in nested dictionaries."""
    system_context = {
        "map_path": "/path/to/map.osm",
    }

    params = {
        "level1": {
            "level2": {
                "map_path": "${system.map_path}",
                "other": "value",
            }
        }
    }

    resolved = _resolve_system_references(params, system_context)

    assert resolved["level1"]["level2"]["map_path"] == "/path/to/map.osm"
    assert resolved["level1"]["level2"]["other"] == "value"


def test_resolve_reference_in_list():
    """Test resolving references in list items."""
    system_context = {
        "map_path": "/path/to/map.osm",
    }

    params = {
        "items": [
            {"map_path": "${system.map_path}"},
            {"other": "value"},
        ]
    }

    resolved = _resolve_system_references(params, system_context)

    assert resolved["items"][0]["map_path"] == "/path/to/map.osm"
    assert resolved["items"][1]["other"] == "value"


def test_invalid_reference_error():
    """Test that invalid references raise clear error messages."""
    system_context = {
        "map_path": "/path/to/map.osm",
    }

    params = {
        "invalid": "${system.nonexistent}",
    }

    with pytest.raises(ValueError) as exc_info:
        _resolve_system_references(params, system_context)

    assert "System reference '${system.nonexistent}' not found" in str(exc_info.value)
    assert "map_path" in str(exc_info.value)  # Should show available keys


def test_invalid_nested_reference_error():
    """Test that invalid nested references raise clear error messages."""
    system_context = {
        "vehicle": {
            "config_path": "/path/to/vehicle.yaml",
        },
    }

    params = {
        "invalid": "${system.vehicle.nonexistent}",
    }

    with pytest.raises(ValueError) as exc_info:
        _resolve_system_references(params, system_context)

    assert "System reference '${system.vehicle.nonexistent}' not found" in str(exc_info.value)


def test_build_system_context(tmp_path):
    """Test building system context from SystemConfig."""
    # Create a temporary vehicle config file
    vehicle_config_path = tmp_path / "vehicle.yaml"
    vehicle_config_path.write_text(
        """
wheelbase: 1.087
width: 1.30
max_steering_angle: 0.64
front_overhang: 0.467
rear_overhang: 0.510
max_velocity: 35.0
max_acceleration: 5.0
mass: 1500.0
inertia: 2500.0
lf: 1.2
lr: 1.3
cf: 80000.0
cr: 80000.0
c_drag: 0.3
c_roll: 0.015
max_drive_force: 5000.0
max_brake_force: 8000.0
"""
    )

    # Create SystemConfig
    system_config = SystemConfig(
        name="test_system",
        module="path/to/module.yaml",
        vehicle={"config_path": str(vehicle_config_path)},
        map_path="experiment/configs/systems/map.osm",
    )

    # Build context
    context = _build_system_context(system_config)

    # Verify map_path is resolved to absolute path
    assert "map_path" in context
    assert context["map_path"].endswith("experiment/configs/systems/map.osm")

    # Verify vehicle_params is loaded as VehicleParameters object
    assert "vehicle_params" in context
    assert isinstance(context["vehicle_params"], VehicleParameters)
    assert context["vehicle_params"].wheelbase == 1.087
    assert context["vehicle_params"].width == 1.30

    # Verify vehicle nested structure
    assert "vehicle" in context
    assert "config_path" in context["vehicle"]
    assert "params" in context["vehicle"]
    assert context["vehicle"]["params"] == context["vehicle_params"]


def test_resolve_nested_reference_direct():
    """Test _resolve_nested_reference function directly."""
    context = {
        "level1": {
            "level2": {
                "level3": "value",
            }
        }
    }

    # Simple reference
    assert _resolve_nested_reference("level1", context) == context["level1"]

    # Nested reference
    assert _resolve_nested_reference("level1.level2.level3", context) == "value"


def test_no_references():
    """Test that params without references are unchanged."""
    system_context = {
        "map_path": "/path/to/map.osm",
    }

    params = {
        "param1": "value1",
        "param2": 42,
        "param3": {"nested": "value"},
        "param4": [1, 2, 3],
    }

    resolved = _resolve_system_references(params, system_context)

    assert resolved == params
