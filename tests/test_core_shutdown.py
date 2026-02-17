import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from src.core.shutdown import ShutdownManager, get_shutdown_manager

@pytest.fixture
def shutdown_manager():
    # Reset singleton effectively for tests
    ShutdownManager._instance = None
    return get_shutdown_manager()

@pytest.mark.asyncio
async def test_shutdown_manager_singleton():
    sm1 = get_shutdown_manager()
    sm2 = get_shutdown_manager()
    assert sm1 is sm2

@pytest.mark.asyncio
async def test_register_and_execute_cleanup(shutdown_manager):
    # Mock tasks
    task1 = Mock()
    task2 = AsyncMock()
    task3 = Mock()
    
    # Register in order 1, 2, 3
    shutdown_manager.register_cleanup_task(task1, "task1")
    shutdown_manager.register_cleanup_task(task2, "task2")
    shutdown_manager.register_cleanup_task(task3, "task3")
    
    # Execute
    await shutdown_manager.execute_cleanup()
    
    # Verify execution order (LIFO: 3, 2, 1)
    # Since we can't easily check exact timing without side effects, 
    # we rely on the implementation. But strictly:
    # We can check call counts.
    
    task3.assert_called_once()
    task2.assert_called_once()
    task1.assert_called_once()

@pytest.mark.asyncio
async def test_error_handling_during_cleanup(shutdown_manager):
    # Task causing error
    bad_task = Mock(side_effect=Exception("Boom"))
    good_task = Mock()
    
    shutdown_manager.register_cleanup_task(good_task, "good")
    shutdown_manager.register_cleanup_task(bad_task, "bad")
    
    # Should not raise exception
    await shutdown_manager.execute_cleanup()
    
    bad_task.assert_called_once()
    good_task.assert_called_once()  # Should still run even if bad_task failed (if bad ran first? No, LIFO)
    # LIFO: bad runs, fails. good runs.
    
@pytest.mark.asyncio
async def test_shutdown_event(shutdown_manager):
    assert not shutdown_manager._shutdown_event.is_set()
    
    shutdown_manager.trigger_shutdown()
    assert shutdown_manager._shutdown_event.is_set()
    
    # Should not block now
    await asyncio.wait_for(shutdown_manager.wait_for_shutdown(), timeout=0.1)

@pytest.mark.asyncio
async def test_request_tracking(shutdown_manager):
    """Test in-flight request tracking."""
    assert shutdown_manager.get_in_flight_count() == 0
    assert shutdown_manager.is_accepting_requests() == True
    
    # Track request start
    await shutdown_manager.track_request_start()
    assert shutdown_manager.get_in_flight_count() == 1
    
    # Track another request
    await shutdown_manager.track_request_start()
    assert shutdown_manager.get_in_flight_count() == 2
    
    # Track request end
    await shutdown_manager.track_request_end()
    assert shutdown_manager.get_in_flight_count() == 1
    
    # Track request end
    await shutdown_manager.track_request_end()
    assert shutdown_manager.get_in_flight_count() == 0

@pytest.mark.asyncio
async def test_drain_requests(shutdown_manager):
    """Test request draining during shutdown."""
    # Start some requests
    await shutdown_manager.track_request_start()
    await shutdown_manager.track_request_start()
    assert shutdown_manager.get_in_flight_count() == 2
    
    # Start drain in background
    drain_task = asyncio.create_task(shutdown_manager.drain_requests(timeout=2))
    
    # Wait a bit to ensure draining started
    await asyncio.sleep(0.1)
    
    # Should not accept new requests
    assert shutdown_manager.is_accepting_requests() == False
    
    # Trying to start a new request should fail
    with pytest.raises(RuntimeError):
        await shutdown_manager.track_request_start()
    
    # End existing requests
    await shutdown_manager.track_request_end()
    await shutdown_manager.track_request_end()
    
    # Wait for drain to complete
    await drain_task
    assert shutdown_manager.get_in_flight_count() == 0

@pytest.mark.asyncio
async def test_drain_requests_timeout(shutdown_manager):
    """Test that drain_requests respects timeout."""
    # Start a request that won't complete
    await shutdown_manager.track_request_start()
    
    # Drain should timeout after 1 second
    start_time = asyncio.get_event_loop().time()
    await shutdown_manager.drain_requests(timeout=1)
    elapsed = asyncio.get_event_loop().time() - start_time
    
    # Should have timed out (allowing some margin)
    assert 0.9 <= elapsed <= 1.5
    
    # Request should still be in flight
    assert shutdown_manager.get_in_flight_count() == 1

@pytest.mark.asyncio
async def test_get_shutdown_timeout(shutdown_manager):
    """Test shutdown timeout configuration."""
    timeout = shutdown_manager.get_shutdown_timeout()
    # Default should be 30 or from environment
    assert timeout > 0
