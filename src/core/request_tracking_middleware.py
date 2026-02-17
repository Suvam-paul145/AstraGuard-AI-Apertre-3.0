"""
Request Tracking Middleware

Middleware to track in-flight requests for graceful shutdown.
Integrates with ShutdownManager to ensure requests complete before shutdown.
"""

import logging
from typing import Callable
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.shutdown import get_shutdown_manager

logger = logging.getLogger(__name__)


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that tracks in-flight requests and rejects new requests during shutdown.
    
    This ensures graceful shutdown by:
    1. Tracking all active requests
    2. Rejecting new requests when shutdown is initiated
    3. Allowing the shutdown manager to drain in-flight requests
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.shutdown_manager = get_shutdown_manager()

    async def dispatch(self, request: Request, call_next: Callable):
        """
        Track request lifecycle.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain
            
        Returns:
            Response or 503 if shutting down
        """
        # Check if server is accepting requests
        if not self.shutdown_manager.is_accepting_requests():
            logger.warning(
                f"Rejecting request to {request.url.path} - server is shutting down"
            )
            return Response(
                content="Server is shutting down. Please try again later.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                headers={"Retry-After": "10"}
            )
        
        # Track request start
        try:
            await self.shutdown_manager.track_request_start()
        except RuntimeError as e:
            # Race condition: shutdown started between check and tracking
            logger.warning(f"Request rejected during shutdown: {e}")
            return Response(
                content="Server is shutting down. Please try again later.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                headers={"Retry-After": "10"}
            )
        
        # Process request
        try:
            response = await call_next(request)
            return response
        finally:
            # Track request end
            await self.shutdown_manager.track_request_end()
