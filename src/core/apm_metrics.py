"""
APM Prometheus Metrics for AstraGuard AI

Defines APM-specific Prometheus metrics for transaction monitoring,
Apdex scoring, throughput measurement, and SLO tracking.

Uses safe metric creation to handle duplicate registration in test reruns,
following the pattern established in astraguard/observability.py.
"""

import logging
from typing import Any, Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    REGISTRY,
)

logger = logging.getLogger(__name__)


# ============================================================================
# SAFE METRIC INITIALIZATION
# ============================================================================


def _safe_create_metric(metric_class: Any, name: str, *args: Any, **kwargs: Any):
    """Safely create a Prometheus metric, handling duplicate registration.

    During test reruns the same metric name may be registered multiple
    times. This helper catches the ValueError and returns the existing
    collector from the registry instead.

    Args:
        metric_class: Prometheus metric class (Counter, Gauge, Histogram, etc.)
        name: Metric name.
        *args: Positional args forwarded to metric_class.
        **kwargs: Keyword args forwarded to metric_class.

    Returns:
        The metric instance (newly created or existing).
    """
    kwargs.setdefault("registry", REGISTRY)
    try:
        return metric_class(name, *args, **kwargs)
    except ValueError:
        # Already registered — retrieve from existing collectors
        for collector in REGISTRY._names_to_collectors.values():
            if hasattr(collector, "_name") and collector._name == name:
                return collector
        # Fallback: try without registry (will re-raise if truly broken)
        logger.warning("Metric %s already registered; reusing existing collector", name)
        kwargs.pop("registry", None)
        return metric_class(name, *args, **kwargs)


# ============================================================================
# TRANSACTION METRICS
# ============================================================================

APM_TRANSACTIONS_TOTAL: Optional[Counter] = _safe_create_metric(
    Counter,
    "astraguard_apm_transactions_total",
    "Total number of APM-tracked transactions",
    ["endpoint", "method", "status"],
)

APM_TRANSACTION_DURATION_SECONDS: Optional[Histogram] = _safe_create_metric(
    Histogram,
    "astraguard_apm_transaction_duration_seconds",
    "Transaction duration in seconds",
    ["endpoint", "method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

APM_SLOW_TRANSACTIONS_TOTAL: Optional[Counter] = _safe_create_metric(
    Counter,
    "astraguard_apm_slow_transactions_total",
    "Total number of transactions exceeding the slow threshold",
    ["endpoint", "method"],
)

APM_ACTIVE_TRANSACTIONS: Optional[Gauge] = _safe_create_metric(
    Gauge,
    "astraguard_apm_active_transactions",
    "Number of currently active transactions",
)

# ============================================================================
# APDEX & SLO METRICS
# ============================================================================

APM_APDEX_SCORE: Optional[Gauge] = _safe_create_metric(
    Gauge,
    "astraguard_apm_apdex_score",
    "Current Apdex score (0.0 - 1.0)",
)

APM_APDEX_SATISFIED: Optional[Counter] = _safe_create_metric(
    Counter,
    "astraguard_apm_apdex_satisfied_total",
    "Total transactions in Apdex satisfied zone (duration <= T)",
)

APM_APDEX_TOLERATING: Optional[Counter] = _safe_create_metric(
    Counter,
    "astraguard_apm_apdex_tolerating_total",
    "Total transactions in Apdex tolerating zone (T < duration <= 4T)",
)

APM_APDEX_FRUSTRATED: Optional[Counter] = _safe_create_metric(
    Counter,
    "astraguard_apm_apdex_frustrated_total",
    "Total transactions in Apdex frustrated zone (duration > 4T)",
)

# ============================================================================
# THROUGHPUT & ERROR BUDGET
# ============================================================================

APM_THROUGHPUT_PER_SECOND: Optional[Gauge] = _safe_create_metric(
    Gauge,
    "astraguard_apm_throughput_per_second",
    "Estimated transactions per second (rolling window)",
)

APM_ERROR_BUDGET_REMAINING: Optional[Gauge] = _safe_create_metric(
    Gauge,
    "astraguard_apm_error_budget_remaining",
    "Remaining error budget ratio (1.0 = full budget, 0.0 = exhausted)",
)

APM_ERRORS_TOTAL: Optional[Counter] = _safe_create_metric(
    Counter,
    "astraguard_apm_errors_total",
    "Total APM-tracked errors",
    ["endpoint", "error_type"],
)
