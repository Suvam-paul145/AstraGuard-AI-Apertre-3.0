"""100% coverage test suite for FeedbackEvent schema."""

import pytest
from datetime import datetime
from models.feedback import FeedbackEvent, FeedbackLabel


class TestFeedbackEvent:
    """Test suite for FeedbackEvent Pydantic model - 12 test cases."""

    @pytest.mark.parametrize("label", list(FeedbackLabel))
    def test_valid_complete_event(self, label: FeedbackLabel):
        """Test valid FeedbackEvent creation with all label types."""
        event = FeedbackEvent(
            fault_id="f001",
            anomaly_type="power",
            recovery_action="cycle",
            label=label,
            mission_phase="NOMINAL_OPS",
        )
        assert event.model_dump_json()
        assert event.label == label

    def test_invalid_label_rejected(self):
        """Test that invalid label values are rejected."""
        with pytest.raises(ValueError):
            FeedbackEvent(
                fault_id="f001",
                anomaly_type="power",
                recovery_action="cycle",
                label="invalid",
                mission_phase="NOMINAL_OPS",
            )

    @pytest.mark.parametrize("phase", ["invalid", "Launch", "", "launch"])
    def test_mission_phase_validation(self, phase: str):
        """Test mission_phase regex validation rejects invalid phases."""
        with pytest.raises(ValueError):
            FeedbackEvent(
                fault_id="f001",
                anomaly_type="x",
                recovery_action="x",
                label=FeedbackLabel.CORRECT,
                mission_phase=phase,
            )

    def test_valid_mission_phases(self):
        """Test all valid mission phases are accepted."""
        valid_phases = [
            "LAUNCH",
            "DEPLOYMENT",
            "NOMINAL_OPS",
            "PAYLOAD_OPS",
            "SAFE_MODE",
        ]
        for phase in valid_phases:
            event = FeedbackEvent(
                fault_id="f001",
                anomaly_type="x",
                recovery_action="x",
                label=FeedbackLabel.CORRECT,
                mission_phase=phase,
            )
            assert event.mission_phase == phase

    def test_confidence_bounds_valid(self):
        """Test confidence_score accepts boundary values."""
        FeedbackEvent(
            fault_id="f001",
            anomaly_type="x",
            recovery_action="x",
            label=FeedbackLabel.CORRECT,
            mission_phase="NOMINAL_OPS",
            confidence_score=0.0,
        )
        FeedbackEvent(
            fault_id="f001",
            anomaly_type="x",
            recovery_action="x",
            label=FeedbackLabel.CORRECT,
            mission_phase="NOMINAL_OPS",
            confidence_score=1.0,
        )

    def test_confidence_bounds_invalid(self):
        """Test confidence_score rejects out-of-bounds values."""
        with pytest.raises(ValueError):
            FeedbackEvent(
                fault_id="f001",
                anomaly_type="x",
                recovery_action="x",
                label=FeedbackLabel.CORRECT,
                mission_phase="NOMINAL_OPS",
                confidence_score=-0.1,
            )
        with pytest.raises(ValueError):
            FeedbackEvent(
                fault_id="f001",
                anomaly_type="x",
                recovery_action="x",
                label=FeedbackLabel.CORRECT,
                mission_phase="NOMINAL_OPS",
                confidence_score=1.1,
            )

    def test_operator_notes_length_validation(self):
        """Test operator_notes max_length validation."""
        with pytest.raises(ValueError):
            FeedbackEvent(
                fault_id="f001",
                anomaly_type="x",
                recovery_action="x",
                label=FeedbackLabel.CORRECT,
                mission_phase="NOMINAL_OPS",
                operator_notes="x" * 501,
            )

    def test_operator_notes_optional(self):
        """Test operator_notes is optional."""
        event = FeedbackEvent(
            fault_id="f001",
            anomaly_type="x",
            recovery_action="x",
            label=FeedbackLabel.CORRECT,
            mission_phase="NOMINAL_OPS",
        )
        assert event.operator_notes is None

    def test_serialization_compact(self):
        """Test JSON serialization is memory efficient."""
        event = FeedbackEvent(
            fault_id="f001",
            anomaly_type="power",
            recovery_action="cycle",
            label=FeedbackLabel.CORRECT,
            mission_phase="NOMINAL_OPS",
        )
        json_str = event.model_dump_json()
        assert len(json_str) < 300  # Memory efficient
        assert "f001" in json_str
        assert "power" in json_str

    def test_field_min_length_validation(self):
        """Test min_length validation for required fields."""
        with pytest.raises(ValueError):
            FeedbackEvent(
                fault_id="",
                anomaly_type="x",
                recovery_action="x",
                label=FeedbackLabel.CORRECT,
                mission_phase="NOMINAL_OPS",
            )

    def test_default_timestamp_generation(self):
        """Test that timestamp defaults to utcnow."""
        event1 = FeedbackEvent(
            fault_id="f001",
            anomaly_type="x",
            recovery_action="x",
            label=FeedbackLabel.CORRECT,
            mission_phase="NOMINAL_OPS",
        )
        event2 = FeedbackEvent(
            fault_id="f002",
            anomaly_type="x",
            recovery_action="x",
            label=FeedbackLabel.CORRECT,
            mission_phase="NOMINAL_OPS",
        )
        assert isinstance(event1.timestamp, datetime)
        assert isinstance(event2.timestamp, datetime)
        assert event1.timestamp <= event2.timestamp

    def test_default_confidence_score(self):
        """Test that confidence_score defaults to 1.0."""
        event = FeedbackEvent(
            fault_id="f001",
            anomaly_type="x",
            recovery_action="x",
            label=FeedbackLabel.CORRECT,
            mission_phase="NOMINAL_OPS",
        )
        assert event.confidence_score == 1.0
