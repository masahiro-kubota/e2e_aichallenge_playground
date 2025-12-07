"""Component core package."""

from core.data import Observation

from .generic_ad_component import GenericADComponent

__all__ = ["GenericADComponent", "Observation"]
