"""
AstraGuard Swarm Module - Multi-Agent Intelligence Framework

Provides data models, serialization, and orchestration for distributed
satellite constellation operations with bandwidth-constrained ISL links.

Issue #397: Data models and serialization foundation
Issue #398: Inter-satellite message bus abstraction
"""

from astraguard.swarm.models import (
    AgentID,
    SatelliteRole,
    HealthSummary,
    SwarmConfig,
)
from astraguard.swarm.serializer import SwarmSerializer
from astraguard.swarm.types import (
    SwarmMessage,
    SwarmTopic,
    QoSLevel,
    TopicFilter,
    SubscriptionID,
    MessageAck,
)
from astraguard.swarm.bus import SwarmMessageBus
from astraguard.swarm.compressor import StateCompressor, CompressionStats

__all__ = [
    # Models (Issue #397)
    "AgentID",
    "SatelliteRole",
    "HealthSummary",
    "SwarmConfig",
    # Serialization (Issue #397)
    "SwarmSerializer",
    # Message types (Issue #398)
    "SwarmMessage",
    "SwarmTopic",
    "QoSLevel",
    "TopicFilter",
    "SubscriptionID",
    "MessageAck",
    # Message bus (Issue #398)
    "SwarmMessageBus",
    # Compression (Issue #399)
    "StateCompressor",
    "CompressionStats",
]
