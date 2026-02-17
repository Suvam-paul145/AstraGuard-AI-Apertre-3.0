"""
APM Middleware for AstraGuard AI FastAPI Application

Automatically instruments every HTTP request with APM transaction tracking.
Works alongside the existing RequestLoggingMiddleware, reusing its correlation
IDs for end-to-end request tracing.

Features:
- Creates a root APM transaction per request
- Records HTTP method, path, status code, and duration
- Tags slow transactions based on configured threshold
- Integrates with OpenTelemetry spans for distributed tracing
- Captures errors and attaches them to the active transaction
"""

import time
import logging
from typing import Callable, Optional, Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.apm import get_apm_manager

logger = logging.getLogger(__name__)

# Endpoints to exclude from APM tracking (health/readiness probes)
EXCLUDED_ENDPOINTS: Set[str] = {
    "/health",
    "/health/live",
    "/health/ready",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class APMMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for automatic APM request instrumentation.

    Wraps every incoming HTTP request in an APM transaction, recording
    duration, status, and error information. Excluded endpoints (health
    checks, docs) are skipped to avoid noise.

    This middleware should be added AFTER RequestLoggingMiddleware so
    that correlation IDs are already available on the request state.

    Usage::

        from core.apm_middleware import APMMiddleware

        app.add_middleware(APMMiddleware)
    """

    def __init__(
        self,
        app: ASGIApp,
        excluded_endpoints: Optional[Set[str]] = None,
    ) -> None:
        """Initialize APM middleware.

        Args:
            app: The ASGI application.
            excluded_endpoints: Optional set of paths to exclude from APM
                tracking. Defaults to health/docs endpoints.
        """
        super().__init__(app)
        self._excluded = excluded_endpoints or EXCLUDED_ENDPOINTS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process an incoming request with APM instrumentation.

        Creates an APM transaction before the request handler executes,
        and closes it after the response is returned — recording status,
        duration, and any errors.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in the chain.

        Returns:
            The HTTP response.
        """
        path = request.url.path

        # Skip excluded endpoints
        if path in self._excluded:
            return await call_next(request)

        apm = get_apm_manager()

        # Don't instrument if APM is not running
        if not apm.is_running:
            return await call_next(request)

        # Build transaction name
        method = request.method
        txn_name = f"{method} {path}"

        # Collect metadata
        correlation_id = getattr(request.state, "correlation_id", None)
        metadata = {
            "http.method": method,
            "http.path": path,
            "http.query": str(request.query_params) if request.query_params else "",
        }
        if correlation_id:
            metadata["correlation_id"] = correlation_id
        if request.client:
            metadata["http.client_host"] = request.client.host

        # Start APM transaction
        txn_id = apm.start_transaction(
            name=txn_name,
            txn_type="request",
            metadata=metadata,
        )

        start_time = time.monotonic()

        try:
            response = await call_next(request)

            # Determine status
            status_code = response.status_code
            if status_code >= 500:
                status = "error"
            elif status_code >= 400:
                status = "client_error"
            else:
                status = "success"

            # End transaction with status
            result = apm.end_transaction(
                txn_id,
                status=status,
                metadata={
                    "http.status_code": str(status_code),
                },
            )

            # Add APM headers to response
            if result:
                response.headers["X-APM-Transaction-ID"] = result.transaction_id
                response.headers["X-APM-Duration-Ms"] = str(
                    round(result.duration_seconds * 1000, 2)
                )
                if result.is_slow:
                    response.headers["X-APM-Slow"] = "true"

            return response

        except Exception as exc:
            # Record error and end transaction
            apm.record_error(txn_id, exc, error_type=type(exc).__name__)
            apm.end_transaction(
                txn_id,
                status="error",
                metadata={"error.type": type(exc).__name__, "error.message": str(exc)},
            )
            raise
