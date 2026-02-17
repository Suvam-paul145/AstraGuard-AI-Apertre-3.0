"""
Tests for Request Tracking Middleware
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from src.core.shutdown import ShutdownManager, get_shutdown_manager
from src.core.request_tracking_middleware import RequestTrackingMiddleware


@pytest.fixture
def shutdown_manager():
    """Reset and return shutdown manager for tests."""
    ShutdownManager._instance = None
    return get_shutdown_manager()


@pytest.fixture
def app(shutdown_manager):
    """Create a test FastAPI app with request tracking middleware."""
    test_app = FastAPI()
    test_app.add_middleware(RequestTrackingMiddleware)
    
    @test_app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    @test_app.get("/slow")
    async def slow_endpoint():
        import asyncio
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


def test_request_rejected_during_shutdown(app, shutdown_manager):
    """Test that requests are rejected when shutdown is in progress."""
    client = TestClient(app)
    
    # Trigger shutdown
    shutdown_manager._accepting_requests = False
    
    # Try to make a request
    response = client.get("/test")
    
    # Should be rejected with 503
    assert response.status_code == 503
    assert "shutting down" in response.text.lower()
    assert response.headers.get("Retry-After") == "10"


@pytest.mark.asyncio
async def test_request_tracking_with_concurrent_requests(app, shutdown_manager):
    """Test request tracking with multiple concurrent requests."""
    from httpx import AsyncClient
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Before requests
        assert shutdown_manager.get_in_flight_count() == 0
        
        # Start multiple concurrent requests
        import asyncio
        tasks = [
            asyncio.create_task(client.get("/slow"))
            for _ in range(3)
        ]
        
        # Give them time to start
        await asyncio.sleep(0.1)
        
        # Should have 3 in-flight requests (or close to it due to timing)
        in_flight = shutdown_manager.get_in_flight_count()
        assert in_flight >= 1  # At least some should be in flight
        
        # Wait for all to complete
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        
        # After all complete
        assert shutdown_manager.get_in_flight_count() == 0


@pytest.mark.asyncio
async def test_request_tracking_during_drain(app, shutdown_manager):
    """Test that drain waits for in-flight requests to complete."""
    from httpx import AsyncClient
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Start a slow request
        import asyncio
        request_task = asyncio.create_task(client.get("/slow"))
        
        # Wait for it to start
        await asyncio.sleep(0.1)
        assert shutdown_manager.get_in_flight_count() == 1
        
        # Start draining (with a reasonable timeout)
        drain_task = asyncio.create_task(shutdown_manager.drain_requests(timeout=2))
        
        # Wait a bit for drain to start
        await asyncio.sleep(0.1)
        
        # Should be draining but not accepting new requests
        assert not shutdown_manager.is_accepting_requests()
        
        # Wait for the request to complete
        response = await request_task
        assert response.status_code == 200
        
        # Wait for drain to complete
        await drain_task
        
        # Should be fully drained
        assert shutdown_manager.get_in_flight_count() == 0
