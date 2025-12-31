"""Diagnostic data structures for AD components."""

from pydantic import BaseModel


class MPCCostDebug(BaseModel):
    """Debug information for MPC costs."""

    lateral_error_cost: float = 0.0
    heading_error_cost: float = 0.0
    steering_cost: float = 0.0
    steering_rate_cost: float = 0.0
    total_cost: float = 0.0
