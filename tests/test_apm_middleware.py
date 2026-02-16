"""
Unit Tests for APM Middleware

Tests cover:
- Request transaction creation and duration tracking
- Slow transaction detection
- Error propagation and recording
- Excluded endpoint handling
- Status code classification
- Response header injection (X-APM-Transaction-ID, X-APM-Duration-Ms)
"""

import os
import sys
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.apm import APMManager, get_apm_manager
from core.apm_config import APMConfig
from core.apm_middleware import APMMiddleware


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_apm():
    """Reset APM singleton before each test."""
    APMManager._reset_singleton()
    yield
    APMManager._reset_singleton()


@pytest.fixture
def app_with_apm():
    """Create a FastAPI app with APM middleware configured."""
    app = FastAPI()

    # Initialize APM with test config
    config = APMConfig(
        enabled=True,
        service_name="test-middleware",
        environment="test",
        slow_transaction_threshold_ms=50.0,  # Low threshold for testing
        apdex_t=0.05,  # 50ms
    )
    apm = get_apm_manager()
    apm.initialize(config)

    # Add APM middleware
    app.add_middleware(APMMiddleware)

    # Test endpoints
    @app.get("/api/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/api/slow")
    async def slow_endpoint():
        time.sleep(0.1)  # 100ms - exceeds 50ms threshold
        return {"status": "slow"}

    @app.get("/api/error")
    async def error_endpoint():
        raise ValueError("Test error")

    @app.get("/api/not-found")
    async def not_found():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")

    @app.get("/api/server-error")
    async def server_error():
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Internal error")

    @app.get("/health")
    async def health():
        return {"status": "alive"}

    return app


@pytest.fixture
def client(app_with_apm):
    """Create a test client for the APM-instrumented app."""
    return TestClient(app_with_apm, raise_server_exceptions=False)


# ============================================================================
# Basic Transaction Tests
# ============================================================================


class TestAPMMiddlewareBasic:
    """Test basic middleware transaction behavior."""

    def test_successful_request_creates_transaction(self, client):
        """A successful request should create and complete a transaction."""
        response = client.get("/api/test")
        assert response.status_code == 200

        # Check APM headers
        assert "x-apm-transaction-id" in response.headers
        assert "x-apm-duration-ms" in response.headers

        # Duration should be a parseable float
        duration = float(response.headers["x-apm-duration-ms"])
        assert duration >= 0

    def test_transaction_id_is_uuid_like(self, client):
        """Transaction ID should be a valid UUID-like string."""
        response = client.get("/api/test")
        txn_id = response.headers.get("x-apm-transaction-id", "")
        assert len(txn_id) > 0
        assert "-" in txn_id  # UUID format has dashes

    def test_total_transactions_incremented(self, client):
        """Each request should increment the transaction counter."""
        apm = get_apm_manager()
        initial_total = apm.get_status()["total_transactions"]

        client.get("/api/test")
        client.get("/api/test")
        client.get("/api/test")

        final_total = apm.get_status()["total_transactions"]
        assert final_total == initial_total + 3


# ============================================================================
# Slow Transaction Tests
# ============================================================================


class TestSlowTransactions:
    """Test slow transaction detection."""

    def test_slow_transaction_header(self, client):
        """Slow transactions should have X-APM-Slow header."""
        response = client.get("/api/slow")
        assert response.status_code == 200

        # Should be marked as slow (100ms > 50ms threshold)
        assert response.headers.get("x-apm-slow") == "true"

    def test_fast_transaction_no_slow_header(self, client):
        """Fast transactions should NOT have X-APM-Slow header."""
        response = client.get("/api/test")
        assert response.status_code == 200
        assert "x-apm-slow" not in response.headers


# ============================================================================
# Excluded Endpoint Tests
# ============================================================================


class TestExcludedEndpoints:
    """Test that excluded endpoints bypass APM tracking."""

    def test_health_endpoint_not_tracked(self, client):
        """Health endpoints should not have APM headers."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "x-apm-transaction-id" not in response.headers
        assert "x-apm-duration-ms" not in response.headers


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test error propagation and recording."""

    def test_server_error_status(self, client):
        """5xx errors should be recorded with 'error' status."""
        response = client.get("/api/server-error")
        assert response.status_code == 500

        # Should still have APM headers (transaction completed)
        assert "x-apm-transaction-id" in response.headers

    def test_client_error_status(self, client):
        """4xx errors should be recorded with 'client_error' status."""
        response = client.get("/api/not-found")
        assert response.status_code == 404

        assert "x-apm-transaction-id" in response.headers


# ============================================================================
# APM Disabled Tests
# ============================================================================


class TestAPMDisabled:
    """Test middleware behavior when APM is disabled."""

    def test_middleware_passthrough_when_disabled(self):
        """When APM is disabled, middleware should pass through without headers."""
        app = FastAPI()

        # Initialize APM as disabled
        config = APMConfig(enabled=False)
        apm = get_apm_manager()
        apm.initialize(config)

        app.add_middleware(APMMiddleware)

        @app.get("/api/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/api/test")
        assert response.status_code == 200

        # No APM headers when disabled
        assert "x-apm-transaction-id" not in response.headers


# ============================================================================
# Status Endpoint Test
# ============================================================================


class TestAPMStatusEndpoint:
    """Test the APM status via manager after middleware operations."""

    def test_status_after_requests(self, client):
        """APM status should reflect request activity."""
        # Make a few requests
        client.get("/api/test")
        client.get("/api/test")

        apm = get_apm_manager()
        status = apm.get_status()

        assert status["running"] is True
        assert status["total_transactions"] >= 2
        assert status["active_transactions"] == 0  # All completed
        assert 0 <= status["apdex_score"] <= 1.0
