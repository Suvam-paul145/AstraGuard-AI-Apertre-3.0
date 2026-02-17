# Graceful Shutdown Implementation

## Overview

This document describes the graceful shutdown implementation for AstraGuard AI backend services, addressing Issue #275.

## Features Implemented

### 1. Signal Handling
- **SIGTERM and SIGINT handlers** automatically registered on startup
- Gracefully triggers shutdown sequence when receiving shutdown signals
- Allows Kubernetes, Docker, and process managers to shut down services cleanly

### 2. Request Draining
- **In-flight request tracking** via middleware
- **Automatic request rejection** when shutdown is initiated (503 Service Unavailable)
- **Configurable timeout** for draining requests (default: 30 seconds)
- Ensures no requests are dropped during shutdown

### 3. Resource Cleanup
- **Database connections** closed gracefully
- **Redis connections** closed properly
- **Background tasks** cancelled and awaited
- **Logs flushed** to ensure no data loss
- **Metrics flushed** before shutdown

### 4. Configuration
- `SHUTDOWN_TIMEOUT` environment variable controls drain timeout
- Default: 30 seconds
- Configurable per deployment environment

## Architecture

### Components

#### 1. ShutdownManager (`src/core/shutdown.py`)
Centralized shutdown coordination singleton that:
- Registers and executes cleanup tasks in LIFO order
- Handles SIGTERM/SIGINT signals
- Tracks in-flight requests
- Manages request draining with timeout
- Provides shutdown event for coordination

#### 2. RequestTrackingMiddleware (`src/core/request_tracking_middleware.py`)
FastAPI middleware that:
- Increments counter when requests start
- Decrements counter when requests complete
- Rejects new requests with 503 during shutdown
- Returns "Retry-After: 10" header for client retry logic

#### 3. Backend Service Integration
Both `backend/main.py` and `api/service.py` integrate graceful shutdown:
- Register signal handlers on startup
- Register cleanup tasks for resources
- Drain requests before cleanup
- Flush logs and metrics
- Execute all cleanup tasks

## Usage

### Environment Configuration

Add to your `.env` file:

```bash
# Graceful shutdown timeout (seconds)
SHUTDOWN_TIMEOUT=30
```

### Backend Service Startup

The services automatically register signal handlers and start tracking requests:

```python
# Signal handlers registered automatically in lifespan
shutdown_manager = get_shutdown_manager()
shutdown_manager.register_signal_handlers()
```

### Shutdown Sequence

When SIGTERM or SIGINT is received:

1. **Signal Handler** triggers shutdown
2. **Stop Accepting Requests** - middleware rejects new requests with 503
3. **Drain In-Flight Requests** - wait up to SHUTDOWN_TIMEOUT for completion
4. **Flush Logs** - ensure all log entries are written
5. **Execute Cleanup Tasks** - run registered cleanup in reverse order:
   - Cancel background tasks
   - Shutdown distributed coordinator
   - Close Redis connections
   - Close database connections
6. **Exit** cleanly

### Registering Custom Cleanup Tasks

```python
from core.shutdown import get_shutdown_manager

shutdown_manager = get_shutdown_manager()

# Sync cleanup
def cleanup_sync():
    print("Cleaning up...")

shutdown_manager.register_cleanup_task(cleanup_sync, "my_cleanup")

# Async cleanup
async def cleanup_async():
    await some_async_cleanup()

shutdown_manager.register_cleanup_task(cleanup_async, "my_async_cleanup")
```

## Testing

### Running Tests

```bash
# Run all shutdown tests
pytest tests/test_core_shutdown.py tests/test_request_tracking_middleware.py -v

# Run specific test
pytest tests/test_core_shutdown.py::test_drain_requests -v
```

### Test Coverage

- **Signal handling** - verify SIGTERM/SIGINT registration
- **Request tracking** - verify counter increments/decrements
- **Request draining** - verify timeout and completion
- **Cleanup execution** - verify LIFO order and error handling
- **Middleware behavior** - verify 503 responses during shutdown

## Deployment Considerations

### Kubernetes

Set appropriate `terminationGracePeriodSeconds` in your pod spec:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: astraguard-backend
spec:
  terminationGracePeriodSeconds: 45  # Should be > SHUTDOWN_TIMEOUT
  containers:
  - name: backend
    image: astraguard:latest
    env:
    - name: SHUTDOWN_TIMEOUT
      value: "30"
```

### Docker

Use `STOPSIGNAL` and `--stop-timeout` appropriately:

```dockerfile
FROM python:3.9
# ... other instructions ...
STOPSIGNAL SIGTERM
```

```bash
docker run --stop-timeout 45 astraguard:latest
```

### Load Balancers

Configure health checks to stop sending traffic during shutdown:
- Backend provides `/health/ready` endpoint
- Load balancer should stop routing when this returns non-200
- Allow time for drain before forceful termination

## Monitoring

### Metrics

Monitor these metrics during shutdown:
- `in_flight_requests` - should drain to zero
- `shutdown_duration_seconds` - time taken for graceful shutdown
- `requests_interrupted` - requests that didn't complete within timeout

### Logs

Look for these log messages:
- `✅ Signal handlers registered (SIGTERM, SIGINT)` - on startup
- `🛑 AstraGuard AI Backend shutting down...` - shutdown initiated
- `⏳ Draining in-flight requests...` - request drain started
- `✅ All in-flight requests completed successfully` - clean drain
- `⚠️  Drain timeout reached. N requests still in-flight.` - timeout warning
- `✅ Graceful shutdown complete` - shutdown finished

## Acceptance Criteria Status

✅ **Catch SIGTERM and SIGINT signals** - Implemented in ShutdownManager
✅ **Drain in-flight requests** - Implemented with RequestTrackingMiddleware
✅ **Close database connections** - Integrated in both services
✅ **Flush logs and metrics** - Integrated in shutdown sequence
✅ **No requests dropped during shutdown** - 503 returned, Retry-After header set
✅ **Clean resource cleanup** - Cleanup tasks registered and executed
✅ **Configurable shutdown timeout** - SHUTDOWN_TIMEOUT environment variable

## Future Enhancements

1. **Metrics Export** - Export shutdown metrics to Prometheus
2. **Graceful Degradation** - Partially degrade service before full shutdown
3. **Zero-Downtime Deployment** - Coordinate with multiple instances
4. **Connection Pooling** - Enhanced pool drain strategies
5. **Circuit Breaker Integration** - Open circuits during shutdown

## References

- Issue #275: Implement graceful shutdown for backend services
- FastAPI Lifespan: https://fastapi.tiangolo.com/advanced/events/
- Uvicorn Graceful Shutdown: https://www.uvicorn.org/deployment/#running-with-gunicorn
- Kubernetes Termination: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination
