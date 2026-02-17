"""
APM Configuration for AstraGuard AI

Centralized configuration for Application Performance Monitoring.
All settings are configurable via environment variables with sensible defaults.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class APMConfig:
    """Configuration for the APM system.

    All fields can be overridden via environment variables prefixed with APM_.

    Attributes:
        enabled: Master toggle for APM (APM_ENABLED, default: True)
        service_name: Service name for traces (APM_SERVICE_NAME)
        service_version: Service version tag (APM_SERVICE_VERSION)
        environment: Deployment environment (APM_ENVIRONMENT)
        sample_rate: Trace sampling rate 0.0-1.0 (APM_SAMPLE_RATE)
        slow_transaction_threshold_ms: Threshold to flag slow transactions
            (APM_SLOW_TRANSACTION_THRESHOLD_MS)
        apdex_t: Apdex threshold in seconds (APM_APDEX_T)
        otel_exporter_endpoint: OTLP exporter endpoint (APM_OTEL_EXPORTER_ENDPOINT)
        max_transactions_tracked: Rolling window size for Apdex calculation
        error_budget_target: SLO target for error budget (0.0-1.0)
    """

    enabled: bool = True
    service_name: str = "astraguard-ai"
    service_version: str = "1.0.0"
    environment: str = "development"
    sample_rate: float = 1.0
    slow_transaction_threshold_ms: float = 500.0
    apdex_t: float = 0.5
    otel_exporter_endpoint: Optional[str] = None
    max_transactions_tracked: int = 1000
    error_budget_target: float = 0.999

    @classmethod
    def from_env(cls) -> "APMConfig":
        """Create APMConfig from environment variables.

        Environment variables:
            APM_ENABLED: "true" or "false" (default: "true")
            APM_SERVICE_NAME: Service name (default: "astraguard-ai")
            APM_SERVICE_VERSION: Version string (default: "1.0.0")
            APM_ENVIRONMENT: Environment name (default: "development")
            APM_SAMPLE_RATE: Float 0.0-1.0 (default: "1.0")
            APM_SLOW_TRANSACTION_THRESHOLD_MS: Float ms (default: "500")
            APM_APDEX_T: Float seconds (default: "0.5")
            APM_OTEL_EXPORTER_ENDPOINT: OTLP endpoint URL (optional)
            APM_MAX_TRANSACTIONS_TRACKED: Int (default: "1000")
            APM_ERROR_BUDGET_TARGET: Float 0.0-1.0 (default: "0.999")

        Returns:
            APMConfig instance with values from environment or defaults.
        """
        config = cls(
            enabled=os.getenv("APM_ENABLED", "true").lower() in ("true", "1", "yes"),
            service_name=os.getenv("APM_SERVICE_NAME", "astraguard-ai"),
            service_version=os.getenv("APM_SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("APM_ENVIRONMENT", "development"),
            sample_rate=_parse_float("APM_SAMPLE_RATE", 1.0, 0.0, 1.0),
            slow_transaction_threshold_ms=_parse_float(
                "APM_SLOW_TRANSACTION_THRESHOLD_MS", 500.0, 0.0
            ),
            apdex_t=_parse_float("APM_APDEX_T", 0.5, 0.001),
            otel_exporter_endpoint=os.getenv("APM_OTEL_EXPORTER_ENDPOINT"),
            max_transactions_tracked=_parse_int(
                "APM_MAX_TRANSACTIONS_TRACKED", 1000, 100
            ),
            error_budget_target=_parse_float(
                "APM_ERROR_BUDGET_TARGET", 0.999, 0.0, 1.0
            ),
        )

        logger.info(
            "APM config loaded: enabled=%s, service=%s, env=%s, sample_rate=%.2f",
            config.enabled,
            config.service_name,
            config.environment,
            config.sample_rate,
        )
        return config

    def to_dict(self) -> dict:
        """Serialize config to dictionary."""
        return {
            "enabled": self.enabled,
            "service_name": self.service_name,
            "service_version": self.service_version,
            "environment": self.environment,
            "sample_rate": self.sample_rate,
            "slow_transaction_threshold_ms": self.slow_transaction_threshold_ms,
            "apdex_t": self.apdex_t,
            "otel_exporter_endpoint": self.otel_exporter_endpoint,
            "max_transactions_tracked": self.max_transactions_tracked,
            "error_budget_target": self.error_budget_target,
        }


def _parse_float(
    env_key: str, default: float, min_val: float = None, max_val: float = None
) -> float:
    """Parse a float environment variable with optional bounds.

    Args:
        env_key: Environment variable name.
        default: Default value if env var is not set or invalid.
        min_val: Optional minimum bound (inclusive).
        max_val: Optional maximum bound (inclusive).

    Returns:
        Parsed and clamped float value.
    """
    raw = os.getenv(env_key)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "Invalid float value for %s: %r, using default %.4f", env_key, raw, default
        )
        return default

    if min_val is not None:
        value = max(min_val, value)
    if max_val is not None:
        value = min(max_val, value)
    return value


def _parse_int(env_key: str, default: int, min_val: int = None) -> int:
    """Parse an integer environment variable with optional minimum.

    Args:
        env_key: Environment variable name.
        default: Default value if env var is not set or invalid.
        min_val: Optional minimum bound (inclusive).

    Returns:
        Parsed and bounded integer value.
    """
    raw = os.getenv(env_key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid int value for %s: %r, using default %d", env_key, raw, default
        )
        return default

    if min_val is not None:
        value = max(min_val, value)
    return value
