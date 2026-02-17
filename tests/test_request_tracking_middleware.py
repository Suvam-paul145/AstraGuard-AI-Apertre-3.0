"""
Tests for Request Tracking Middleware

Note: These tests focus on the core functionality rather than exact timing of concurrent requests,
as timing-based assertions can be flaky in test environments.
"""

import pytest
import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from src.core.shutdown import ShutdownManager, get_shutdown_manager
from src.core.request_tracking_middleware import RequestTrackingMiddleware


@pytest.fixture(autouse=True)
def reset_shutdown_manager():
    """Reset shutdown manager before each test."""
    ShutdownManager._instance = None
    yield
    # Clean up after test
    ShutdownManager._instance = None


@pytest.fixture
def shutdown_manager():
    """Get the shutdown manager instance for tests."""
    return get_shutdown_manager()


@pytest.fixture
def app():
    """Create a test FastAPI app with request tracking middleware."""
    test_app = FastAPI()
    test_app.add_middleware(RequestTrackingMiddleware)
    
    @test_app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    @test_app.get("/slow")
    async def slow_endpoint():
        await asyncio.sleep(0.5)
        return {"status": "completed"}
    
    return test_app


def test_request_tracking_normal_flow(app, shutdown_manager):
    """Test that requests are tracked correctly during normal operation."""
    client = TestClient(app)
    
    # Before request
    assert shutdown_manager.get_in_flight_count() == 0
    
    # Make a request
    response = client.get("/test")
    assert response.status_code == 200
    
    # After request completes
    assert shutdown_manager.get_in_flight_count() == 0


def test_accepting_requests_flag(shutdown_manager):
    """Test that the accepting_requests flag works correctly."""
    # Initially should be accepting
    assert shutdown_manager.is_accepting_requests() == True
    
    # After stopping
    shutdown_manager._accepting_requests = False
    assert shutdown_manager.is_accepting_requests() == False


def test_shutdown_timeout_config(shutdown_manager):
    """Test that shutdown timeout is configurable."""
    timeout = shutdown_manager.get_shutdown_timeout()
    assert timeout > 0
    assert isinstance(timeout, int)


@pytest.mark.asyncio
async def test_drain_requests_basic(shutdown_manager):
    """Test basic drain requests functionality."""
    # No in-flight requests
    assert shutdown_manager.get_in_flight_count() == 0
    
    # Drain should complete immediately
    await shutdown_manager.drain_requests(timeout=1)
    
    # Should no longer be accepting requests
    assert not shutdown_manager.is_accepting_requests()



