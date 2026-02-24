"""Topology package."""

from .base import BaseTopology
from .sequential import DEFAULT_SEQUENTIAL_ROLES, SequentialTopology

__all__ = ["BaseTopology", "DEFAULT_SEQUENTIAL_ROLES", "SequentialTopology"]
