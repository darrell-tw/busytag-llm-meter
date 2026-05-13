"""Base classes for usage data sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UsageSnapshot:
    source: str
    primary_used_pct: float
    primary_resets_at: Optional[int]  # Unix timestamp
    secondary_used_pct: Optional[float] = None
    secondary_resets_at: Optional[int] = None
    plan_type: Optional[str] = None
    ts: float = field(default_factory=__import__("time").time)


class UsageSource(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Machine-readable source identifier (e.g. 'claude_code')."""

    @abstractmethod
    def read(self) -> Optional[UsageSnapshot]:
        """Return the latest snapshot from shared state, or None if unavailable."""

    @abstractmethod
    def stale_after_seconds(self) -> int:
        """Age in seconds after which a snapshot should be considered stale."""
