"""
Unit Tests for APM (Application Performance Monitoring) Manager

Tests cover:
- Configuration loading from defaults and environment variables
- Transaction lifecycle (start → end → recorded)
- Apdex score calculation (satisfied / tolerating / frustrated)
- Error recording on active transactions
- Singleton pattern
- Throughput and error budget tracking
- Shutdown and cleanup
"""

import os
import time
import pytest
from unittest.mock import patch, MagicMock

import sys

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


from core.apm_config import APMConfig, _parse_float, _parse_int
from core.apm import APMManager, get_apm_manager, TransactionResult


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_apm_singleton():
    """Reset APM singleton before each test to ensure isolation."""
    APMManager._reset_singleton()
    yield
    APMManager._reset_singleton()


@pytest.fixture
def apm_config():
    """Create a test APM config with sensible defaults."""
    return APMConfig(
        enabled=True,
        service_name="test-service",
        environment="test",
        sample_rate=1.0,
        slow_transaction_threshold_ms=100.0,
        apdex_t=0.1,
        otel_exporter_endpoint=None,  # No external exporter in tests
        max_transactions_tracked=100,
        error_budget_target=0.99,
    )


@pytest.fixture
def apm(apm_config):
    """Create and initialize an APM manager for testing."""
    manager = APMManager()
    manager.initialize(apm_config)
    yield manager
    manager.reset()


# ============================================================================
# APMConfig Tests
# ============================================================================


class TestAPMConfig:
    """Test APM configuration loading and validation."""

    def test_default_config(self):
        """Default config should have sensible values."""
        config = APMConfig()
        assert config.enabled is True
        assert config.service_name == "astraguard-ai"
        assert config.sample_rate == 1.0
        assert config.apdex_t == 0.5
        assert config.error_budget_target == 0.999

    def test_from_env_defaults(self):
        """from_env() with no env vars should use defaults."""
        config = APMConfig.from_env()
        assert config.enabled is True
        assert config.service_name == "astraguard-ai"

    def test_from_env_custom_values(self):
        """from_env() should read custom environment variables."""
        env = {
            "APM_ENABLED": "false",
            "APM_SERVICE_NAME": "my-service",
            "APM_SAMPLE_RATE": "0.5",
            "APM_APDEX_T": "0.25",
            "APM_SLOW_TRANSACTION_THRESHOLD_MS": "200",
            "APM_ENVIRONMENT": "staging",
        }
        with patch.dict(os.environ, env):
            config = APMConfig.from_env()
            assert config.enabled is False
            assert config.service_name == "my-service"
            assert config.sample_rate == 0.5
            assert config.apdex_t == 0.25
            assert config.slow_transaction_threshold_ms == 200.0
            assert config.environment == "staging"

    def test_sample_rate_clamping(self):
        """Sample rate should be clamped between 0.0 and 1.0."""
        with patch.dict(os.environ, {"APM_SAMPLE_RATE": "5.0"}):
            config = APMConfig.from_env()
            assert config.sample_rate == 1.0

        with patch.dict(os.environ, {"APM_SAMPLE_RATE": "-1.0"}):
            config = APMConfig.from_env()
            assert config.sample_rate == 0.0

    def test_invalid_float_falls_back_to_default(self):
        """Invalid float values should fall back to defaults."""
        with patch.dict(os.environ, {"APM_SAMPLE_RATE": "not_a_number"}):
            config = APMConfig.from_env()
            assert config.sample_rate == 1.0

    def test_to_dict(self):
        """to_dict() should return all config keys."""
        config = APMConfig()
        d = config.to_dict()
        assert "enabled" in d
        assert "service_name" in d
        assert "apdex_t" in d
        assert "error_budget_target" in d


class TestParseHelpers:
    """Test _parse_float and _parse_int helpers."""

    def test_parse_float_default(self):
        """Should return default when env var is not set."""
        assert _parse_float("NONEXISTENT_VAR", 3.14) == 3.14

    def test_parse_float_valid(self):
        """Should parse valid float values."""
        with patch.dict(os.environ, {"TEST_FLOAT": "2.5"}):
            assert _parse_float("TEST_FLOAT", 0.0) == 2.5

    def test_parse_float_invalid(self):
        """Should return default for invalid float values."""
        with patch.dict(os.environ, {"TEST_FLOAT": "abc"}):
            assert _parse_float("TEST_FLOAT", 1.0) == 1.0

    def test_parse_int_default(self):
        """Should return default when env var is not set."""
        assert _parse_int("NONEXISTENT_VAR", 42) == 42

    def test_parse_int_valid(self):
        """Should parse valid integer values."""
        with patch.dict(os.environ, {"TEST_INT": "100"}):
            assert _parse_int("TEST_INT", 0) == 100

    def test_parse_int_with_minimum(self):
        """Should enforce minimum bound."""
        with patch.dict(os.environ, {"TEST_INT": "5"}):
            assert _parse_int("TEST_INT", 50, min_val=10) == 10


# ============================================================================
# APMManager Tests
# ============================================================================


class TestAPMManager:
    """Test core APM manager functionality."""

    def test_singleton_pattern(self, apm_config):
        """APMManager should be a singleton."""
        m1 = APMManager()
        m2 = APMManager()
        assert m1 is m2

    def test_initialize(self, apm):
        """Manager should be running after initialization."""
        assert apm.is_running is True
        status = apm.get_status()
        assert status["enabled"] is True
        assert status["running"] is True
        assert status["service_name"] == "test-service"

    def test_initialize_disabled(self):
        """Manager with APM disabled should not be running."""
        config = APMConfig(enabled=False)
        manager = APMManager()
        manager.initialize(config)
        assert manager.is_running is False

    def test_shutdown(self, apm):
        """Shutdown should stop the manager."""
        assert apm.is_running is True
        apm.shutdown()
        assert apm.is_running is False

    def test_transaction_lifecycle(self, apm):
        """Start and end a transaction successfully."""
        txn_id = apm.start_transaction("test-op", "request")
        assert txn_id != ""
        assert len(txn_id) > 0

        # Should have 1 active transaction
        status = apm.get_status()
        assert status["active_transactions"] == 1

        # End the transaction
        result = apm.end_transaction(txn_id, status="success")
        assert result is not None
        assert isinstance(result, TransactionResult)
        assert result.status == "success"
        assert result.duration_seconds >= 0

        # No active transactions
        status = apm.get_status()
        assert status["active_transactions"] == 0

    def test_transaction_with_metadata(self, apm):
        """Transactions should carry metadata."""
        txn_id = apm.start_transaction(
            "GET /api/test",
            "request",
            metadata={"http.method": "GET", "http.path": "/api/test"},
        )
        result = apm.end_transaction(txn_id, status="success")
        assert result is not None
        assert result.name == "GET /api/test"

    def test_end_nonexistent_transaction(self, apm):
        """Ending a non-existent transaction should return None."""
        result = apm.end_transaction("nonexistent-id")
        assert result is None

    def test_end_transaction_empty_id(self, apm):
        """Ending with empty ID should return None."""
        result = apm.end_transaction("")
        assert result is None

    def test_transaction_not_running(self):
        """Transactions should not be created when APM is not running."""
        manager = APMManager()
        # Not initialized -> not running
        txn_id = manager.start_transaction("test")
        assert txn_id == ""

    def test_error_recording(self, apm):
        """Errors should be recorded against transactions."""
        txn_id = apm.start_transaction("test-error", "request")
        apm.record_error(txn_id, ValueError("test error"), "ValueError")
        result = apm.end_transaction(txn_id, status="error")
        assert result is not None
        assert result.status == "error"

    def test_error_recording_nonexistent_txn(self, apm):
        """Recording error on non-existent transaction should not raise."""
        apm.record_error("nonexistent", ValueError("test"))
        # Should not raise

    def test_multiple_concurrent_transactions(self, apm):
        """Multiple transactions can be active simultaneously."""
        txn1 = apm.start_transaction("op-1")
        txn2 = apm.start_transaction("op-2")
        txn3 = apm.start_transaction("op-3")

        status = apm.get_status()
        assert status["active_transactions"] == 3

        apm.end_transaction(txn1, status="success")
        apm.end_transaction(txn2, status="success")
        apm.end_transaction(txn3, status="error")

        status = apm.get_status()
        assert status["active_transactions"] == 0
        assert status["total_transactions"] == 3
        assert status["total_errors"] == 1

    def test_shutdown_clears_active_transactions(self, apm):
        """Shutdown should clear all active transactions."""
        apm.start_transaction("op-1")
        apm.start_transaction("op-2")
        apm.shutdown()
        status = apm.get_status()
        assert status["active_transactions"] == 0


# ============================================================================
# Apdex Tests
# ============================================================================


class TestApdex:
    """Test Apdex score calculation."""

    def test_perfect_apdex(self, apm):
        """All fast transactions should give Apdex = 1.0."""
        for _ in range(10):
            txn_id = apm.start_transaction("fast-op")
            # End immediately (duration << apdex_t of 0.1s)
            apm.end_transaction(txn_id, status="success")

        apdex = apm.get_apdex_score()
        assert apdex == 1.0

    def test_initial_apdex(self, apm):
        """Apdex should be 1.0 when no transactions have been recorded."""
        assert apm.get_apdex_score() == 1.0

    def test_apdex_classification_satisfied(self, apm):
        """Transactions under T threshold should be classified as satisfied."""
        # apdex_t is 0.1s; a near-instant transaction should be satisfied
        result = apm._classify_apdex(0.05)
        assert result == "satisfied"

    def test_apdex_classification_tolerating(self, apm):
        """Transactions between T and 4T should be tolerating."""
        result = apm._classify_apdex(0.3)  # Between 0.1 and 0.4
        assert result == "tolerating"

    def test_apdex_classification_frustrated(self, apm):
        """Transactions over 4T should be frustrated."""
        result = apm._classify_apdex(0.5)  # Over 0.4 (4 * 0.1)
        assert result == "frustrated"

    def test_mixed_apdex(self, apm):
        """Mixed transaction performance should produce intermediate Apdex."""
        # Manually update apdex window
        apm._apdex_window.clear()
        for _ in range(5):
            apm._update_apdex_window("satisfied")
        for _ in range(3):
            apm._update_apdex_window("tolerating")
        for _ in range(2):
            apm._update_apdex_window("frustrated")

        # Apdex = (5 + 3/2) / 10 = 6.5/10 = 0.65
        apdex = apm.get_apdex_score()
        assert apdex == 0.65


# ============================================================================
# Error Budget Tests
# ============================================================================


class TestErrorBudget:
    """Test error budget calculation."""

    def test_full_error_budget(self, apm):
        """All successful transactions should give full error budget."""
        for _ in range(10):
            txn_id = apm.start_transaction("success-op")
            apm.end_transaction(txn_id, status="success")

        status = apm.get_status()
        assert status["total_transactions"] == 10
        assert status["total_errors"] == 0

    def test_error_budget_decreases(self, apm):
        """Errors should consume the error budget."""
        # SLO target is 0.99, so allowed_error_rate = 0.01
        for i in range(100):
            txn_id = apm.start_transaction(f"op-{i}")
            status_val = "error" if i < 5 else "success"  # 5% error rate
            apm.end_transaction(txn_id, status=status_val)

        status = apm.get_status()
        assert status["total_errors"] == 5
        # 5% error rate vs 1% allowed = 500% consumed = budget remaining near 0
        # but clamped to 0


# ============================================================================
# Status & Introspection Tests
# ============================================================================


class TestAPMStatus:
    """Test status reporting."""

    def test_get_status_structure(self, apm):
        """get_status() should return all expected keys."""
        status = apm.get_status()
        expected_keys = [
            "enabled", "running", "service_name", "environment",
            "otel_available", "active_transactions", "total_transactions",
            "total_errors", "apdex_score", "apdex_threshold",
            "slow_threshold_ms", "error_budget_target", "config",
        ]
        for key in expected_keys:
            assert key in status, f"Missing key: {key}"

    def test_config_property(self, apm):
        """config property should return the current APMConfig."""
        config = apm.config
        assert config.service_name == "test-service"


# ============================================================================
# Span Tests
# ============================================================================


class TestSpanManagement:
    """Test span creation context manager."""

    def test_create_span_no_tracer(self, apm):
        """create_span should yield None when tracer is not available."""
        apm._tracer = None
        with apm.create_span("test-span") as span:
            assert span is None

    def test_create_span_not_running(self):
        """create_span should yield None when APM is not running."""
        manager = APMManager()
        with manager.create_span("test-span") as span:
            assert span is None


# ============================================================================
# get_apm_manager Tests
# ============================================================================


class TestModuleLevelAccess:
    """Test module-level access function."""

    def test_get_apm_manager_returns_singleton(self):
        """get_apm_manager() should always return the same instance."""
        m1 = get_apm_manager()
        m2 = get_apm_manager()
        assert m1 is m2
