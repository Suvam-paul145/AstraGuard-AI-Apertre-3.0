"""
Shutdown Manager Module

Centralized registry for cleanup tasks to ensure graceful application shutdown.
Handles SIGTERM and SIGINT signals, drains in-flight requests, and manages
cleanup tasks with configurable timeouts.
"""

import asyncio
import logging
import signal
import os
from typing import List, Callable, Awaitable, Union, Optional

logger = logging.getLogger(__name__)

class ShutdownManager:
    """Manages graceful shutdown tasks with request draining and signal handling."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ShutdownManager, cls).__new__(cls)
            cls._instance._tasks = []
            cls._instance._shutdown_event = asyncio.Event()
            cls._instance._in_flight_requests = 0
            cls._instance._request_lock = asyncio.Lock()
            cls._instance._accepting_requests = True
            cls._instance._shutdown_timeout = int(os.getenv("SHUTDOWN_TIMEOUT", "30"))
            cls._instance._signals_registered = False
        return cls._instance

    def register_cleanup_task(self, task: Union[Callable[[], None], Callable[[], Awaitable[None]]], name: str = "task"):
        """Register a cleanup task (sync or async)."""
        self._tasks.append((name, task))
        logger.debug(f"Registered cleanup task: {name}")

    def register_signal_handlers(self):
        """Register SIGTERM and SIGINT signal handlers for graceful shutdown."""
        if self._signals_registered:
            logger.debug("Signal handlers already registered")
            return
        
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            self.trigger_shutdown()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        self._signals_registered = True
        logger.info("Signal handlers registered for SIGTERM and SIGINT")

    async def track_request_start(self):
        """Increment in-flight request counter."""
        async with self._request_lock:
            if not self._accepting_requests:
                raise RuntimeError("Server is shutting down, not accepting new requests")
            self._in_flight_requests += 1
            logger.debug(f"Request started. In-flight: {self._in_flight_requests}")

    async def track_request_end(self):
        """Decrement in-flight request counter."""
        async with self._request_lock:
            self._in_flight_requests = max(0, self._in_flight_requests - 1)
            logger.debug(f"Request ended. In-flight: {self._in_flight_requests}")

    def get_in_flight_count(self) -> int:
        """Get current number of in-flight requests."""
        return self._in_flight_requests

    def is_accepting_requests(self) -> bool:
        """Check if server is accepting new requests."""
        return self._accepting_requests

    async def drain_requests(self, timeout: Optional[int] = None):
        """
        Wait for all in-flight requests to complete with timeout.
        
        Args:
            timeout: Maximum time to wait in seconds. Uses SHUTDOWN_TIMEOUT if not provided.
        """
        if timeout is None:
            timeout = self._shutdown_timeout
        
        logger.info("Stopping acceptance of new requests...")
        async with self._request_lock:
            self._accepting_requests = False
        
        logger.info(f"Draining {self._in_flight_requests} in-flight requests (timeout: {timeout}s)...")
        
        start_time = asyncio.get_event_loop().time()
        while self._in_flight_requests > 0:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(
                    f"Drain timeout reached. {self._in_flight_requests} requests still in-flight. "
                    "Proceeding with shutdown anyway."
                )
                break
            
            await asyncio.sleep(0.1)
        
        if self._in_flight_requests == 0:
            logger.info("All in-flight requests completed successfully")
        else:
            logger.warning(f"{self._in_flight_requests} requests were interrupted during shutdown")

    async def execute_cleanup(self):
        """Execute all registered cleanup tasks."""
        logger.info("Executing shutdown cleanup tasks...")
        
        # Run in reverse order of registration
        for name, task in reversed(self._tasks):
            try:
                logger.info(f"Cleaning up: {name}")
                if asyncio.iscoroutinefunction(task):
                    await task()
                else:
                    task()
            except Exception as e:
                logger.error(f"Error during cleanup of {name}: {e}", exc_info=True)
                
        logger.info("Shutdown cleanup complete.")

    def trigger_shutdown(self):
        """Trigger the shutdown event."""
        logger.info("Shutdown triggered.")
        self._shutdown_event.set()

    async def wait_for_shutdown(self):
        """Wait for the shutdown event."""
        await self._shutdown_event.wait()

    def get_shutdown_timeout(self) -> int:
        """Get configured shutdown timeout in seconds."""
        return self._shutdown_timeout

def get_shutdown_manager() -> ShutdownManager:
    """Get the singleton ShutdownManager instance."""
    return ShutdownManager()
