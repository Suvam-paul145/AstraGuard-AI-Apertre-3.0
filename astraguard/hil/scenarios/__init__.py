"""HIL test scenario schema and management."""

from .schema import (
    FaultType,
    SatelliteConfig,
    FaultInjection,
    SuccessCriteria,
    Scenario,
    load_scenario,
    validate_scenario,
    SCENARIO_SCHEMA,
)

__all__ = [
    "FaultType",
    "SatelliteConfig",
    "FaultInjection",
    "SuccessCriteria",
    "Scenario",
    "load_scenario",
    "validate_scenario",
    "SCENARIO_SCHEMA",
]
