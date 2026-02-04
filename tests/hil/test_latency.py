"""Unit tests for latency.py module."""

import pytest
import tempfile
import os
from unittest.mock import patch
from src.astraguard.hil.metrics.latency import LatencyCollector, LatencyMeasurement


class TestLatencyMeasurement:
    """Test LatencyMeasurement dataclass."""

    def test_latency_measurement_creation(self):
        """Test creating a LatencyMeasurement instance."""
        measurement = LatencyMeasurement(
            timestamp=1234567890.0,
            metric_type="fault_detection",
            satellite_id="SAT1",
            duration_ms=150.5,
            scenario_time_s=100.0
        )

        assert measurement.timestamp == 1234567890.0
        assert measurement.metric_type == "fault_detection"
        assert measurement.satellite_id == "SAT1"
        assert measurement.duration_ms == 150.5
        assert measurement.scenario_time_s == 100.0

    def test_latency_measurement_asdict(self):
        """Test asdict conversion for CSV export."""
        measurement = LatencyMeasurement(
            timestamp=1234567890.0,
            metric_type="agent_decision",
            satellite_id="SAT2",
            duration_ms=200.0,
            scenario_time_s=150.0
        )

        data = measurement.__dict__
        expected = {
            "timestamp": 1234567890.0,
            "metric_type": "agent_decision",
            "satellite_id": "SAT2",
            "duration_ms": 200.0,
            "scenario_time_s": 150.0
        }
        assert data == expected


class TestLatencyCollector:
    """Test LatencyCollector class."""

    def test_initialization(self):
        """Test collector initialization."""
        collector = LatencyCollector()
        assert collector.measurements == []
        assert collector._measurement_log == {}
        assert len(collector) == 0

    def test_record_fault_detection(self):
        """Test recording fault detection latency."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.5)

        assert len(collector.measurements) == 1
        measurement = collector.measurements[0]
        assert measurement.metric_type == "fault_detection"
        assert measurement.satellite_id == "SAT1"
        assert measurement.duration_ms == 150.5
        assert measurement.scenario_time_s == 100.0
        assert measurement.timestamp == 1234567890.0
        assert collector._measurement_log["fault_detection"] == 1

    def test_record_agent_decision(self):
        """Test recording agent decision latency."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567891.0):
            collector.record_agent_decision("SAT2", 200.0, 75.0)

        assert len(collector.measurements) == 1
        measurement = collector.measurements[0]
        assert measurement.metric_type == "agent_decision"
        assert measurement.satellite_id == "SAT2"
        assert measurement.duration_ms == 75.0
        assert measurement.scenario_time_s == 200.0
        assert measurement.timestamp == 1234567891.0
        assert collector._measurement_log["agent_decision"] == 1

    def test_record_recovery_action(self):
        """Test recording recovery action latency."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567892.0):
            collector.record_recovery_action("SAT3", 300.0, 250.0)

        assert len(collector.measurements) == 1
        measurement = collector.measurements[0]
        assert measurement.metric_type == "recovery_action"
        assert measurement.satellite_id == "SAT3"
        assert measurement.duration_ms == 250.0
        assert measurement.scenario_time_s == 300.0
        assert measurement.timestamp == 1234567892.0
        assert collector._measurement_log["recovery_action"] == 1

    def test_multiple_recordings(self):
        """Test recording multiple measurements."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=[1234567890.0, 1234567891.0, 1234567892.0]):
            collector.record_fault_detection("SAT1", 100.0, 150.0)
            collector.record_agent_decision("SAT1", 200.0, 75.0)
            collector.record_recovery_action("SAT2", 300.0, 250.0)

        assert len(collector.measurements) == 3
        assert collector._measurement_log["fault_detection"] == 1
        assert collector._measurement_log["agent_decision"] == 1
        assert collector._measurement_log["recovery_action"] == 1

    def test_get_stats_empty(self):
        """Test get_stats with no measurements."""
        collector = LatencyCollector()
        stats = collector.get_stats()
        assert stats == {}

    def test_get_stats_single_measurement(self):
        """Test get_stats with single measurement per type."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.0)

        stats = collector.get_stats()
        assert "fault_detection" in stats
        fd_stats = stats["fault_detection"]
        assert fd_stats["count"] == 1
        assert fd_stats["mean_ms"] == 150.0
        assert fd_stats["p50_ms"] == 150.0
        assert fd_stats["p95_ms"] == 150.0
        assert fd_stats["p99_ms"] == 150.0
        assert fd_stats["max_ms"] == 150.0
        assert fd_stats["min_ms"] == 150.0

    def test_get_stats_multiple_measurements(self):
        """Test get_stats with multiple measurements."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=[1234567890.0, 1234567891.0, 1234567892.0]):
            collector.record_fault_detection("SAT1", 100.0, 100.0)
            collector.record_fault_detection("SAT1", 200.0, 200.0)
            collector.record_fault_detection("SAT1", 300.0, 300.0)

        stats = collector.get_stats()
        fd_stats = stats["fault_detection"]
        assert fd_stats["count"] == 3
        assert fd_stats["mean_ms"] == 200.0
        assert fd_stats["p50_ms"] == 200.0  # sorted: 100, 200, 300 -> median 200
        assert fd_stats["p95_ms"] == 300.0  # 95th percentile
        assert fd_stats["p99_ms"] == 300.0  # 99th percentile
        assert fd_stats["max_ms"] == 300.0
        assert fd_stats["min_ms"] == 100.0

    def test_get_stats_by_satellite_empty(self):
        """Test get_stats_by_satellite with no measurements."""
        collector = LatencyCollector()
        stats = collector.get_stats_by_satellite()
        assert stats == {}

    def test_get_stats_by_satellite_single_satellite(self):
        """Test get_stats_by_satellite with one satellite."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=[1234567890.0, 1234567891.0]):
            collector.record_fault_detection("SAT1", 100.0, 150.0)
            collector.record_agent_decision("SAT1", 200.0, 75.0)

        stats = collector.get_stats_by_satellite()
        assert "SAT1" in stats
        sat1_stats = stats["SAT1"]
        assert "fault_detection" in sat1_stats
        assert "agent_decision" in sat1_stats

        fd_stats = sat1_stats["fault_detection"]
        assert fd_stats["count"] == 1
        assert fd_stats["mean_ms"] == 150.0
        assert fd_stats["p50_ms"] == 150.0
        assert fd_stats["p95_ms"] == 150.0
        assert fd_stats["max_ms"] == 150.0

    def test_get_stats_by_satellite_multiple_satellites(self):
        """Test get_stats_by_satellite with multiple satellites."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=[1234567890.0, 1234567891.0, 1234567892.0]):
            collector.record_fault_detection("SAT1", 100.0, 150.0)
            collector.record_fault_detection("SAT2", 200.0, 200.0)
            collector.record_agent_decision("SAT1", 300.0, 75.0)

        stats = collector.get_stats_by_satellite()
        assert len(stats) == 2
        assert "SAT1" in stats
        assert "SAT2" in stats

        sat1_fd = stats["SAT1"]["fault_detection"]
        assert sat1_fd["count"] == 1
        assert sat1_fd["mean_ms"] == 150.0

        sat2_fd = stats["SAT2"]["fault_detection"]
        assert sat2_fd["count"] == 1
        assert sat2_fd["mean_ms"] == 200.0

    def test_export_csv(self):
        """Test CSV export functionality."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.5)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name

        try:
            collector.export_csv(tmp_path)

            # Verify file exists and has content
            assert os.path.exists(tmp_path)

            with open(tmp_path, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 2  # header + 1 data row
                assert "timestamp,metric_type,satellite_id,duration_ms,scenario_time_s" in lines[0]
                assert "1234567890.0,fault_detection,SAT1,150.5,100.0" in lines[1]

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_get_summary_empty(self):
        """Test get_summary with no measurements."""
        collector = LatencyCollector()
        summary = collector.get_summary()
        expected = {"total_measurements": 0, "metrics": {}}
        assert summary == expected

    def test_get_summary_with_data(self):
        """Test get_summary with measurements."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=[1234567890.0, 1234567891.0]):
            collector.record_fault_detection("SAT1", 100.0, 150.0)
            collector.record_agent_decision("SAT2", 200.0, 75.0)

        summary = collector.get_summary()
        assert summary["total_measurements"] == 2
        assert summary["measurement_types"]["fault_detection"] == 1
        assert summary["measurement_types"]["agent_decision"] == 1
        assert "stats" in summary
        assert "stats_by_satellite" in summary

    def test_reset(self):
        """Test reset functionality."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.0)

        assert len(collector.measurements) == 1
        assert collector._measurement_log["fault_detection"] == 1

        collector.reset()
        assert len(collector.measurements) == 0
        assert collector._measurement_log == {}

    def test_len(self):
        """Test __len__ method."""
        collector = LatencyCollector()
        assert len(collector) == 0

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.0)

        assert len(collector) == 1

        collector.reset()
        assert len(collector) == 0

    def test_edge_case_single_measurement_stats_by_satellite(self):
        """Test stats_by_satellite with single measurement per satellite."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.0)

        stats = collector.get_stats_by_satellite()
        sat1_fd = stats["SAT1"]["fault_detection"]
        assert sat1_fd["count"] == 1
        assert sat1_fd["mean_ms"] == 150.0
        assert sat1_fd["p50_ms"] == 150.0
        assert sat1_fd["p95_ms"] == 150.0
        assert sat1_fd["max_ms"] == 150.0

    def test_edge_case_empty_latencies_in_stats_by_satellite(self):
        """Test stats_by_satellite handles empty latencies gracefully."""
        collector = LatencyCollector()

        # This shouldn't happen in practice, but test robustness
        # Manually add a measurement with duration 0 to test edge
        measurement = LatencyMeasurement(
            timestamp=1234567890.0,
            metric_type="fault_detection",
            satellite_id="SAT1",
            duration_ms=0.0,
            scenario_time_s=100.0
        )
        collector.measurements.append(measurement)

        stats = collector.get_stats_by_satellite()
        sat1_fd = stats["SAT1"]["fault_detection"]
        assert sat1_fd["count"] == 1
        assert sat1_fd["mean_ms"] == 0.0
        assert sat1_fd["max_ms"] == 0.0
