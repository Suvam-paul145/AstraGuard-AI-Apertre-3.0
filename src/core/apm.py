"""
APM (Application Performance Monitoring) Manager for AstraGuard AI

Central APM engine providing:
- OpenTelemetry distributed tracing with configurable exporters
- Transaction lifecycle management (start / end / error)
- Real-time Apdex score calculation
- Throughput and error budget tracking
- Span creation for nested operation tracing

Usage:
    from core.apm import get_apm_manager

    apm = get_apm_manager()
    apm.initialize()

    # Track a transaction
    txn_id = apm.start_transaction("process_telemetry", "request")
    try:
        result = do_work()
        apm.end_transaction(txn_id, status="success")
    except Exception as e:
        apm.record_error(txn_id, e)
        apm.end_transaction(txn_id, status="error")
"""

import time
import uuid
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Deque
from contextlib import contextmanager

from core.apm_config import APMConfig
from core.apm_metrics import (
    APM_TRANSACTIONS_TOTAL,
    APM_TRANSACTION_DURATION_SECONDS,
    APM_SLOW_TRANSACTIONS_TOTAL,
    APM_ACTIVE_TRANSACTIONS,
    APM_APDEX_SCORE,
    APM_APDEX_SATISFIED,
    APM_APDEX_TOLERATING,
    APM_APDEX_FRUSTRATED,
    APM_THROUGHPUT_PER_SECOND,
    APM_ERROR_BUDGET_REMAINING,
    APM_ERRORS_TOTAL,
)

logger = logging.getLogger(__name__)

# Optional OpenTelemetry imports — graceful degradation if not installed
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.info("OpenTelemetry SDK not available; tracing will be disabled")


# ============================================================================
# TRANSACTION DATA
# ============================================================================


@dataclass
class Transaction:
    """Represents an in-flight APM transaction.

    Attributes:
        id: Unique transaction identifier.
        name: Human-readable name (e.g., endpoint path).
        type: Transaction type (request, background, scheduled).
        start_time: Monotonic start timestamp.
        wall_start: Wall-clock start time (for logging).
        span: Optional OpenTelemetry span.
        metadata: Arbitrary key-value metadata.
    """

    id: str
    name: str
    type: str = "request"
    start_time: float = 0.0
    wall_start: float = 0.0
    span: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionResult:
    """Result of a completed transaction.

    Attributes:
        transaction_id: ID of the completed transaction.
        name: Transaction name.
        duration_seconds: Duration in seconds.
        status: Outcome status (success, error, timeout).
        apdex_zone: Apdex zone classification.
        is_slow: Whether the transaction exceeded the slow threshold.
    """

    transaction_id: str
    name: str
    duration_seconds: float
    status: str
    apdex_zone: str
    is_slow: bool


# ============================================================================
# APM MANAGER
# ============================================================================


class APMManager:
    """Central Application Performance Monitoring manager.

    Thread-safe singleton that manages the full APM lifecycle including
    OpenTelemetry tracing setup, transaction tracking, Apdex scoring,
    and throughput/error-budget calculation.

    The manager gracefully degrades when OpenTelemetry is not installed,
    still providing Prometheus metrics and Apdex scoring.
    """

    _instance: Optional["APMManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "APMManager":
        """Singleton pattern — one APMManager per process."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        """Initialize APM manager (idempotent)."""
        if self._initialized:
            return
        self._initialized = True

        self._config: APMConfig = APMConfig()
        self._tracer: Optional[Any] = None
        self._tracer_provider: Optional[Any] = None

        # Active transactions (thread-safe via lock)
        self._transactions: Dict[str, Transaction] = {}
        self._txn_lock = threading.Lock()

        # Apdex tracking (rolling window)
        self._apdex_window: Deque[str] = deque(maxlen=1000)
        self._apdex_lock = threading.Lock()

        # Throughput tracking
        self._throughput_window: Deque[float] = deque(maxlen=1000)
        self._throughput_lock = threading.Lock()

        # Error tracking for error budget
        self._total_transactions: int = 0
        self._total_errors: int = 0
        self._budget_lock = threading.Lock()

        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self, config: Optional[APMConfig] = None) -> None:
        """Initialize the APM system with configuration.

        Sets up OpenTelemetry tracing (if available) and resets all
        internal counters.

        Args:
            config: APMConfig instance; if None, loads from env vars.
        """
        self._config = config or APMConfig.from_env()

        if not self._config.enabled:
            logger.info("APM is disabled via configuration")
            self._running = False
            return

        self._apdex_window = deque(maxlen=self._config.max_transactions_tracked)

        # Set up OpenTelemetry tracing
        if OTEL_AVAILABLE:
            self._setup_tracing()

        self._running = True
        logger.info(
            "APM initialized: service=%s, env=%s, otel=%s",
            self._config.service_name,
            self._config.environment,
            OTEL_AVAILABLE,
        )

    def _setup_tracing(self) -> None:
        """Configure OpenTelemetry TracerProvider and span processor."""
        resource = Resource.create(
            {
                "service.name": self._config.service_name,
                "service.version": self._config.service_version,
                "deployment.environment": self._config.environment,
            }
        )

        self._tracer_provider = TracerProvider(resource=resource)

        # Use OTLP exporter if endpoint configured, else console (dev)
        if self._config.otel_exporter_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(
                    endpoint=self._config.otel_exporter_endpoint,
                )
                logger.info(
                    "OTLP exporter configured: %s",
                    self._config.otel_exporter_endpoint,
                )
            except ImportError:
                logger.warning(
                    "OTLP exporter not installed; falling back to console exporter"
                )
                exporter = ConsoleSpanExporter()
        else:
            exporter = ConsoleSpanExporter()

        self._tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(self._tracer_provider)
        self._tracer = trace.get_tracer(
            self._config.service_name,
            self._config.service_version,
        )

    def shutdown(self) -> None:
        """Gracefully shut down the APM system.

        Flushes pending spans and cleans up resources.
        """
        self._running = False

        if self._tracer_provider and hasattr(self._tracer_provider, "shutdown"):
            try:
                self._tracer_provider.shutdown()
                logger.info("APM tracer provider shut down")
            except Exception as exc:
                logger.warning("Error shutting down tracer provider: %s", exc)

        with self._txn_lock:
            active_count = len(self._transactions)
            if active_count > 0:
                logger.warning(
                    "APM shutdown with %d active transactions", active_count
                )
            self._transactions.clear()

        logger.info("APM shut down")

    # ------------------------------------------------------------------
    # Transaction Management
    # ------------------------------------------------------------------

    def start_transaction(
        self,
        name: str,
        txn_type: str = "request",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a new APM transaction.

        Creates a transaction record and optionally an OpenTelemetry span.

        Args:
            name: Transaction name (e.g., "GET /api/telemetry").
            txn_type: Transaction type ("request", "background", "scheduled").
            metadata: Optional key-value metadata.

        Returns:
            Transaction ID string.
        """
        if not self._running:
            return ""

        txn_id = str(uuid.uuid4())
        span = None

        if self._tracer:
            span = self._tracer.start_span(
                name=name,
                attributes={
                    "transaction.id": txn_id,
                    "transaction.type": txn_type,
                    **(metadata or {}),
                },
            )

        txn = Transaction(
            id=txn_id,
            name=name,
            type=txn_type,
            start_time=time.monotonic(),
            wall_start=time.time(),
            span=span,
            metadata=metadata or {},
        )

        with self._txn_lock:
            self._transactions[txn_id] = txn

        if APM_ACTIVE_TRANSACTIONS:
            APM_ACTIVE_TRANSACTIONS.inc()

        return txn_id

    def end_transaction(
        self,
        txn_id: str,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[TransactionResult]:
        """End an active transaction and record metrics.

        Args:
            txn_id: Transaction ID from start_transaction().
            status: Outcome status ("success", "error", "timeout").
            metadata: Optional additional metadata.

        Returns:
            TransactionResult if transaction was found, None otherwise.
        """
        if not txn_id or not self._running:
            return None

        with self._txn_lock:
            txn = self._transactions.pop(txn_id, None)

        if txn is None:
            logger.debug("Transaction %s not found (already ended?)", txn_id)
            return None

        duration = time.monotonic() - txn.start_time

        if APM_ACTIVE_TRANSACTIONS:
            APM_ACTIVE_TRANSACTIONS.dec()

        # End OpenTelemetry span
        if txn.span:
            if metadata:
                for key, value in metadata.items():
                    txn.span.set_attribute(f"result.{key}", str(value))
            txn.span.set_attribute("transaction.status", status)
            txn.span.set_attribute("transaction.duration_ms", duration * 1000)
            txn.span.end()

        # Classify Apdex zone
        apdex_zone = self._classify_apdex(duration)

        # Check slow transaction
        is_slow = (duration * 1000) > self._config.slow_transaction_threshold_ms

        # Record Prometheus metrics
        self._record_metrics(txn, duration, status, apdex_zone, is_slow)

        # Update tracking windows
        self._update_apdex_window(apdex_zone)
        self._update_throughput(time.time())
        self._update_error_budget(status)

        return TransactionResult(
            transaction_id=txn_id,
            name=txn.name,
            duration_seconds=duration,
            status=status,
            apdex_zone=apdex_zone,
            is_slow=is_slow,
        )

    def record_error(
        self,
        txn_id: str,
        exception: Optional[Exception] = None,
        error_type: str = "unknown",
    ) -> None:
        """Record an error against an active transaction.

        Args:
            txn_id: Transaction ID.
            exception: Optional exception instance.
            error_type: Error classification string.
        """
        if not txn_id or not self._running:
            return

        with self._txn_lock:
            txn = self._transactions.get(txn_id)

        if txn is None:
            return

        endpoint = txn.name

        if txn.span and exception:
            txn.span.set_attribute("error", True)
            txn.span.set_attribute("error.type", error_type)
            txn.span.set_attribute("error.message", str(exception))

        if APM_ERRORS_TOTAL:
            APM_ERRORS_TOTAL.labels(endpoint=endpoint, error_type=error_type).inc()

    # ------------------------------------------------------------------
    # Span Management
    # ------------------------------------------------------------------

    @contextmanager
    def create_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Context manager for creating a nested tracing span.

        Args:
            name: Span name.
            attributes: Optional span attributes.

        Yields:
            The span object (or None if tracing is unavailable).
        """
        if not self._tracer or not self._running:
            yield None
            return

        span = self._tracer.start_span(name=name, attributes=attributes or {})
        try:
            yield span
        except Exception as exc:
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(exc))
            raise
        finally:
            span.end()

    # ------------------------------------------------------------------
    # Apdex Calculation
    # ------------------------------------------------------------------

    def _classify_apdex(self, duration_seconds: float) -> str:
        """Classify a transaction duration into an Apdex zone.

        Apdex zones:
        - Satisfied: duration <= T
        - Tolerating: T < duration <= 4T
        - Frustrated: duration > 4T

        Args:
            duration_seconds: Transaction duration.

        Returns:
            "satisfied", "tolerating", or "frustrated".
        """
        t = self._config.apdex_t
        if duration_seconds <= t:
            return "satisfied"
        elif duration_seconds <= 4 * t:
            return "tolerating"
        else:
            return "frustrated"

    def _update_apdex_window(self, zone: str) -> None:
        """Add a zone classification to the rolling Apdex window."""
        with self._apdex_lock:
            self._apdex_window.append(zone)
            self._recalculate_apdex()

    def _recalculate_apdex(self) -> None:
        """Recalculate and update the Apdex score gauge.

        Apdex = (satisfied + tolerating / 2) / total
        """
        if not self._apdex_window:
            return

        total = len(self._apdex_window)
        satisfied = sum(1 for z in self._apdex_window if z == "satisfied")
        tolerating = sum(1 for z in self._apdex_window if z == "tolerating")

        apdex = (satisfied + tolerating / 2) / total

        if APM_APDEX_SCORE:
            APM_APDEX_SCORE.set(round(apdex, 4))

    def get_apdex_score(self) -> float:
        """Get the current Apdex score.

        Returns:
            Apdex score between 0.0 and 1.0.
        """
        with self._apdex_lock:
            if not self._apdex_window:
                return 1.0
            total = len(self._apdex_window)
            satisfied = sum(1 for z in self._apdex_window if z == "satisfied")
            tolerating = sum(1 for z in self._apdex_window if z == "tolerating")
            return round((satisfied + tolerating / 2) / total, 4)

    # ------------------------------------------------------------------
    # Metrics Recording
    # ------------------------------------------------------------------

    def _record_metrics(
        self,
        txn: Transaction,
        duration: float,
        status: str,
        apdex_zone: str,
        is_slow: bool,
    ) -> None:
        """Record all Prometheus metrics for a completed transaction."""
        endpoint = txn.name
        method = txn.metadata.get("http.method", txn.type)

        if APM_TRANSACTIONS_TOTAL:
            APM_TRANSACTIONS_TOTAL.labels(
                endpoint=endpoint, method=method, status=status
            ).inc()

        if APM_TRANSACTION_DURATION_SECONDS:
            APM_TRANSACTION_DURATION_SECONDS.labels(
                endpoint=endpoint, method=method
            ).observe(duration)

        if is_slow and APM_SLOW_TRANSACTIONS_TOTAL:
            APM_SLOW_TRANSACTIONS_TOTAL.labels(
                endpoint=endpoint, method=method
            ).inc()

        # Apdex zone counters
        if apdex_zone == "satisfied" and APM_APDEX_SATISFIED:
            APM_APDEX_SATISFIED.inc()
        elif apdex_zone == "tolerating" and APM_APDEX_TOLERATING:
            APM_APDEX_TOLERATING.inc()
        elif apdex_zone == "frustrated" and APM_APDEX_FRUSTRATED:
            APM_APDEX_FRUSTRATED.inc()

    def _update_throughput(self, timestamp: float) -> None:
        """Update throughput gauge based on rolling window of timestamps."""
        with self._throughput_lock:
            self._throughput_window.append(timestamp)

            # Calculate throughput from window
            if len(self._throughput_window) >= 2:
                window_duration = (
                    self._throughput_window[-1] - self._throughput_window[0]
                )
                if window_duration > 0:
                    throughput = len(self._throughput_window) / window_duration
                    if APM_THROUGHPUT_PER_SECOND:
                        APM_THROUGHPUT_PER_SECOND.set(round(throughput, 2))

    def _update_error_budget(self, status: str) -> None:
        """Update error budget remaining gauge.

        Error budget = 1.0 - (actual_error_rate / allowed_error_rate)
        Where allowed_error_rate = 1.0 - SLO_target
        """
        with self._budget_lock:
            self._total_transactions += 1
            if status in ("error", "failure", "timeout"):
                self._total_errors += 1

            if self._total_transactions > 0:
                actual_error_rate = self._total_errors / self._total_transactions
                allowed_error_rate = 1.0 - self._config.error_budget_target

                if allowed_error_rate > 0:
                    budget_consumed = actual_error_rate / allowed_error_rate
                    budget_remaining = max(0.0, 1.0 - budget_consumed)
                else:
                    budget_remaining = 0.0 if self._total_errors > 0 else 1.0

                if APM_ERROR_BUDGET_REMAINING:
                    APM_ERROR_BUDGET_REMAINING.set(round(budget_remaining, 4))

    # ------------------------------------------------------------------
    # Status & Introspection
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Get current APM status and statistics.

        Returns:
            Dictionary with APM health information.
        """
        with self._txn_lock:
            active_count = len(self._transactions)

        with self._budget_lock:
            total_txn = self._total_transactions
            total_err = self._total_errors

        return {
            "enabled": self._config.enabled,
            "running": self._running,
            "service_name": self._config.service_name,
            "environment": self._config.environment,
            "otel_available": OTEL_AVAILABLE,
            "active_transactions": active_count,
            "total_transactions": total_txn,
            "total_errors": total_err,
            "apdex_score": self.get_apdex_score(),
            "apdex_threshold": self._config.apdex_t,
            "slow_threshold_ms": self._config.slow_transaction_threshold_ms,
            "error_budget_target": self._config.error_budget_target,
            "config": self._config.to_dict(),
        }

    @property
    def config(self) -> APMConfig:
        """Get the current APM configuration."""
        return self._config

    @property
    def is_running(self) -> bool:
        """Check if APM is currently active."""
        return self._running

    # ------------------------------------------------------------------
    # Reset (for testing)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all APM state. Intended for testing only."""
        self.shutdown()
        self._transactions.clear()
        self._apdex_window.clear()
        self._throughput_window.clear()
        self._total_transactions = 0
        self._total_errors = 0
        self._running = False
        self._initialized = False

    @classmethod
    def _reset_singleton(cls) -> None:
        """Reset the singleton instance. Intended for testing only."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.reset()
                cls._instance = None


# ============================================================================
# MODULE-LEVEL ACCESS
# ============================================================================

_apm_manager: Optional[APMManager] = None
_module_lock = threading.Lock()


def get_apm_manager() -> APMManager:
    """Get the global APMManager singleton.

    Returns:
        The APMManager instance.
    """
    global _apm_manager
    with _module_lock:
        if _apm_manager is None:
            _apm_manager = APMManager()
        return _apm_manager
