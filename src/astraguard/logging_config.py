"""
AstraGuard Structured Logging Module
JSON-based structured logging for enterprise observability (Azure Monitor compatible)
"""

import logging
import json
import sys
import os
from datetime import datetime
from typing import Any, Dict, Optional
import structlog
from pythonjsonlogger import jsonlogger
from core.secrets import get_secret
from functools import lru_cache
import asyncio

# Cache secret retrieval to avoid repeated I/O
@lru_cache(maxsize=32)
def _cached_get_secret(key: str, default=None):
    """Cached wrapper for get_secret to reduce I/O overhead."""
    try:
        return get_secret(key, default)
    except Exception:
        return default

# ============================================================================
# STRUCTURED LOGGING CONFIGURATION
# ============================================================================

def setup_json_logging(
    log_level: str = "INFO",
    service_name: str = "astra-guard",
    environment: str = None
):
    if environment is None:
        environment = _cached_get_secret("environment", "development")
    """
    Setup JSON structured logging for production environments
    Compatible with Azure Monitor, ELK Stack, Splunk, etc.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        service_name: Name of the service
        environment: Environment name (development, staging, production)
    """
    try:
        # Validate log_level
        if not hasattr(logging, log_level.upper()):
            raise ValueError(f"Invalid log level: {log_level}")

        # Configure structlog for structured output
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.ExceptionRenderer(),
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Configure root logger with JSON handler
        json_handler = logging.StreamHandler(sys.stdout)
        json_formatter = jsonlogger.JsonFormatter(
            fmt='%(timestamp)s %(level)s %(name)s %(message)s',
            timestamp=True
        )
        json_handler.setFormatter(json_formatter)

        # Configure Python logging
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))
        root_logger.handlers.clear()
        root_logger.addHandler(json_handler)

        # Add global context with safe secret retrieval
        try:
            app_version = get_secret("app_version", "1.0.0")
        except (KeyError, ValueError, Exception) as e:
            app_version = "1.0.0"
            print(f"Warning: Failed to retrieve app_version secret: {e}", file=sys.stderr)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            service=service_name,
            environment=environment,
            version=app_version
        )

    except (AttributeError, ImportError, ValueError) as e:
        # Fallback to basic logging if JSON setup fails
        print(f"Warning: JSON logging setup failed ({type(e).__name__}): {e}. Falling back to basic logging.", file=sys.stderr)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    except Exception as e:
        # Catch any other unexpected exceptions
        print(f"Error: Unexpected error during logging setup ({type(e).__name__}): {e}. Using default logging.", file=sys.stderr)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Bound structlog logger instance
    """
    return structlog.get_logger(name)


# ============================================================================
# LOGGING CONTEXT MANAGERS
# ============================================================================

class LogContext:
    """Context manager for scoped logging context"""
    
    def __init__(self, logger: structlog.BoundLogger, **context):
        self.logger = logger
        self.context = context
    
    def __enter__(self):
        self.logger = self.logger.bind(**self.context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.logger.error(
                "context_error",
                error_type=exc_type.__name__,
                error_message=str(exc_val)
            )


def log_request(
    logger: structlog.BoundLogger,
    method: str,
    endpoint: str,
    status: int,
    duration_ms: float,
    **extra
):
    """
    Log HTTP request with structured data
    
    Args:
        logger: Structlog logger instance
        method: HTTP method
        endpoint: Request endpoint
        status: HTTP status code
        duration_ms: Request duration in milliseconds
        **extra: Additional context fields
    """
    logger.info(
        "http_request",
        method=method,
        endpoint=endpoint,
        status=status,
        duration_ms=round(duration_ms, 2),
        **extra
    )


def log_error(
    logger: structlog.BoundLogger,
    error: Exception,
    context: str,
    **extra
):
    """
    Log error with full context and stack trace
    
    Args:
        logger: Structlog logger instance
        error: Exception instance
        context: Context description
        **extra: Additional context fields
    """
    logger.error(
        context,
        error_type=type(error).__name__,
        error_message=str(error),
        exc_info=True,
        **extra
    )


def log_detection(
    logger: structlog.BoundLogger,
    severity: str,
    detected_type: str,
    confidence: float,
    **extra
):
    """
    Log anomaly/detection event
    
    Args:
        logger: Structlog logger instance
        severity: Severity level (critical, warning, info)
        detected_type: Type of anomaly detected
        confidence: Confidence score (0.0-1.0)
        **extra: Additional context fields
    """
    logger.info(
        "anomaly_detected",
        severity=severity,
        type=detected_type,
        confidence=round(confidence, 3),
        **extra
    )


def log_circuit_breaker_event(
    logger: structlog.BoundLogger,
    event: str,
    breaker_name: str,
    state: str,
    reason: Optional[str] = None,
    **extra
):
    """
    Log circuit breaker state changes
    
    Args:
        logger: Structlog logger instance
        event: Event type (opened, closed, reset, half_open)
        breaker_name: Name of circuit breaker
        state: Current state
        reason: Reason for state change
        **extra: Additional context fields
    """
    logger.warning(
        "circuit_breaker_event",
        event=event,
        breaker=breaker_name,
        state=state,
        reason=reason,
        **extra
    )


def log_retry_event(
    logger: structlog.BoundLogger,
    endpoint: str,
    attempt: int,
    status: str,
    delay_ms: Optional[float] = None,
    **extra
):
    """
    Log retry attempt
    
    Args:
        logger: Structlog logger instance
        endpoint: Endpoint being retried
        attempt: Attempt number
        status: Status (retrying, success, exhausted)
        delay_ms: Delay before next retry in milliseconds
        **extra: Additional context fields
    """
    level = "info" if status == "retrying" else "warning"
    getattr(logger, level)(
        "retry_event",
        endpoint=endpoint,
        attempt=attempt,
        status=status,
        delay_ms=delay_ms,
        **extra
    )


def log_recovery_action(
    logger: structlog.BoundLogger,
    action_type: str,
    status: str,
    component: str,
    duration_ms: Optional[float] = None,
    **extra
):
    """
    Log recovery/remediation action
    
    Args:
        logger: Structlog logger instance
        action_type: Type of recovery action
        status: Status (started, completed, failed)
        component: Component being recovered
        duration_ms: Duration of recovery in milliseconds
        **extra: Additional context fields
    """
    logger.info(
        "recovery_action",
        action=action_type,
        status=status,
        component=component,
        duration_ms=duration_ms,
        **extra
    )


def log_performance_metric(
    logger: structlog.BoundLogger,
    metric_name: str,
    value: float,
    unit: str = "ms",
    threshold: Optional[float] = None,
    **extra
):
    """
    Log performance metric

    Args:
        logger: Structlog logger instance
        metric_name: Name of metric
        value: Metric value
        unit: Unit of measurement
        threshold: SLO threshold for comparison
        **extra: Additional context fields
    """
    alert = False
    if threshold is not None and value > threshold:
        alert = True
        log_level = "warning"
    else:
        log_level = "info"

    getattr(logger, log_level)(
        "performance_metric",
        metric=metric_name,
        value=round(value, 2),
        unit=unit,
        threshold=threshold,
        alert=alert,
        **extra
    )


# ============================================================================
# ASYNC LOGGING FUNCTIONS
# ============================================================================

async def async_log_request(
    logger: structlog.BoundLogger,
    method: str,
    endpoint: str,
    status: int,
    duration_ms: float,
    **extra
):
    """
    Async version of log_request to avoid blocking in async contexts.

    Args:
        logger: Structlog logger instance
        method: HTTP method
        endpoint: Request endpoint
        status: HTTP status code
        duration_ms: Request duration in milliseconds
        **extra: Additional context fields
    """
    await asyncio.to_thread(
        log_request, logger, method, endpoint, status, duration_ms, **extra
    )


async def async_log_error(
    logger: structlog.BoundLogger,
    error: Exception,
    context: str,
    **extra
):
    """
    Async version of log_error.

    Args:
        logger: Structlog logger instance
        error: Exception instance
        context: Context description
        **extra: Additional context fields
    """
    await asyncio.to_thread(log_error, logger, error, context, **extra)


async def async_log_detection(
    logger: structlog.BoundLogger,
    severity: str,
    detected_type: str,
    confidence: float,
    **extra
):
    """
    Async version of log_detection.

    Args:
        logger: Structlog logger instance
        severity: Severity level
        detected_type: Type of anomaly detected
        confidence: Confidence score
        **extra: Additional context fields
    """
    await asyncio.to_thread(log_detection, logger, severity, detected_type, confidence, **extra)


# ============================================================================
# FILTERING AND UTILITIES
# ============================================================================

def set_log_level(level: str):
    """Change logging level at runtime"""
    try:
        if not hasattr(logging, level.upper()):
            raise ValueError(f"Invalid log level: {level}")
        logging.getLogger().setLevel(getattr(logging, level))
    except (AttributeError, ValueError) as e:
        print(f"Warning: Failed to set log level to '{level}': {e}. Log level unchanged.", file=sys.stderr)


def clear_context():
    """Clear all context variables"""
    structlog.contextvars.clear_contextvars()


def bind_context(**context):
    """Add context to all future log entries"""
    structlog.contextvars.bind_contextvars(**context)


def unbind_context(*keys):
    """Remove context variables"""
    structlog.contextvars.unbind_contextvars(*keys)


# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize on import with error handling
try:
    enable_json = _cached_get_secret("enable_json_logging", False)
    if enable_json:
        setup_json_logging()
except (KeyError, ValueError, Exception) as e:
    print(f"Warning: Failed to initialize JSON logging on import: {e}. Using default logging.", file=sys.stderr)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
