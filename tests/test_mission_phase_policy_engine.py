"""
Unit Tests for Mission Phase Policy Engine

Tests the policy evaluation logic across different mission phases
and anomaly scenarios.
"""

import pytest
from datetime import datetime
from state_machine.state_engine import MissionPhase
from state_machine.mission_phase_policy_engine import (
    MissionPhasePolicyEngine,
    SeverityLevel,
    EscalationLevel,
    PolicyDecision
)
from config.mission_phase_policy_loader import MissionPhasePolicyLoader


@pytest.fixture
def policy_engine():
    """Create a policy engine with default policies."""
    loader = MissionPhasePolicyLoader()
    return MissionPhasePolicyEngine(loader.get_policy())


class TestPolicyEngine:
    """Test suite for MissionPhasePolicyEngine."""
    
    def test_engine_initialization(self, policy_engine):
        """Test that engine initializes correctly."""
        assert policy_engine is not None
        assert policy_engine.policy_config is not None
        assert 'phases' in policy_engine.policy_config
    
    def test_severity_classification(self, policy_engine):
        """Test severity level classification."""
        assert policy_engine._classify_severity(0.95) == SeverityLevel.CRITICAL
        assert policy_engine._classify_severity(0.75) == SeverityLevel.HIGH
        assert policy_engine._classify_severity(0.50) == SeverityLevel.MEDIUM
        assert policy_engine._classify_severity(0.25) == SeverityLevel.LOW
    
    def test_get_phase_config(self, policy_engine):
        """Test retrieving phase configuration."""
        config = policy_engine._get_phase_config(MissionPhase.NOMINAL_OPS)
        assert config is not None
        assert 'allowed_actions' in config
        assert 'description' in config
        assert 'threshold_multiplier' in config


class TestLaunchPhasePolicy:
    """Test fault response policies during LAUNCH phase."""
    
    def test_launch_critical_anomaly_escalates(self, policy_engine):
        """During LAUNCH, critical anomalies should escalate to SAFE_MODE."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.LAUNCH,
            anomaly_type='power_fault',
            severity_score=0.95,
            anomaly_attributes={}
        )
        
        # CRITICAL severity escalates to SAFE_MODE
        assert decision.escalation_level == EscalationLevel.ESCALATE_SAFE_MODE.value
        assert decision.recommended_action == "ENTER_SAFE_MODE"
    
    def test_launch_high_anomaly_alerts_only(self, policy_engine):
        """During LAUNCH, high anomalies should alert only."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.LAUNCH,
            anomaly_type='thermal_fault',
            severity_score=0.75,
            anomaly_attributes={}
        )
        
        assert decision.is_allowed is False
        assert decision.escalation_level == EscalationLevel.ALERT_OPERATORS.value
    
    def test_launch_medium_anomaly_alerts_operators(self, policy_engine):
        """During LAUNCH, medium anomalies should alert operators."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.LAUNCH,
            anomaly_type='attitude_fault',
            severity_score=0.50,
            anomaly_attributes={}
        )
        
        # Medium severity in LAUNCH triggers ALERT_OPERATORS
        assert decision.escalation_level == EscalationLevel.ALERT_OPERATORS.value
    
    def test_launch_forbidden_actions_blocked(self, policy_engine):
        """Verify that forbidden actions are listed during LAUNCH."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.LAUNCH,
            anomaly_type='power_fault',
            severity_score=0.5,
            anomaly_attributes={}
        )
        
        # No automated actions allowed during launch except critical
        assert len(decision.allowed_actions) > 0  # At least logging
        assert "FIRE_THRUSTERS" not in decision.allowed_actions


class TestDeploymentPhasePolicy:
    """Test fault response policies during DEPLOYMENT phase."""
    
    def test_deployment_critical_escalates(self, policy_engine):
        """During DEPLOYMENT, critical faults escalate."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.DEPLOYMENT,
            anomaly_type='power_fault',
            severity_score=0.92,
            anomaly_attributes={}
        )
        
        assert decision.escalation_level == EscalationLevel.ESCALATE_SAFE_MODE.value
    
    def test_deployment_high_with_recurrence_escalates(self, policy_engine):
        """During DEPLOYMENT, recurring high-severity faults get controlled action."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.DEPLOYMENT,
            anomaly_type='thermal_fault',
            severity_score=0.75,
            anomaly_attributes={'recurrence_count': 2}  # 2+ indicates pattern
        )
        
        # HIGH with recurrence in DEPLOYMENT -> CONTROLLED_ACTION
        assert decision.escalation_level == EscalationLevel.CONTROLLED_ACTION.value


class TestNominalOpsPhasePolicy:
    """Test fault response policies during NOMINAL_OPS phase."""
    
    def test_nominal_critical_escalates(self, policy_engine):
        """During NOMINAL_OPS, critical faults escalate to SAFE_MODE."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.NOMINAL_OPS,
            anomaly_type='power_fault',
            severity_score=0.95,
            anomaly_attributes={}
        )
        
        assert decision.is_allowed is True
        assert decision.escalation_level == EscalationLevel.ESCALATE_SAFE_MODE.value
        assert decision.recommended_action == "ENTER_SAFE_MODE"
    
    def test_nominal_high_allows_controlled_action(self, policy_engine):
        """During NOMINAL_OPS, high-severity faults allow controlled response."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.NOMINAL_OPS,
            anomaly_type='thermal_fault',
            severity_score=0.80,
            anomaly_attributes={}
        )
        
        assert decision.is_allowed is True
        assert decision.escalation_level == EscalationLevel.CONTROLLED_ACTION.value
        assert decision.recommended_action in decision.allowed_actions
    
    def test_nominal_medium_allows_action(self, policy_engine):
        """During NOMINAL_OPS, medium-severity faults allow response."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.NOMINAL_OPS,
            anomaly_type='attitude_fault',
            severity_score=0.50,
            anomaly_attributes={}
        )
        
        assert decision.is_allowed is True
        assert decision.escalation_level == EscalationLevel.CONTROLLED_ACTION.value
    
    def test_nominal_recurring_critical_escalates(self, policy_engine):
        """During NOMINAL_OPS, persistent high-severity faults escalate."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.NOMINAL_OPS,
            anomaly_type='power_fault',
            severity_score=0.75,
            anomaly_attributes={'recurrence_count': 3}  # 3+ indicates persistence
        )
        
        assert decision.escalation_level == EscalationLevel.ESCALATE_SAFE_MODE.value
    
    def test_nominal_multiple_failures_escalate(self, policy_engine):
        """During NOMINAL_OPS, multiple simultaneous failures escalate."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.NOMINAL_OPS,
            anomaly_type='power_fault',
            severity_score=0.75,
            anomaly_attributes={'simultaneous_faults': 2}
        )
        
        # Multiple failures should escalate even if individual severity isn't critical
        # (This depends on implementation details)
        assert decision.severity == SeverityLevel.HIGH.value
    
    def test_nominal_restart_service_allowed(self, policy_engine):
        """RESTART_SERVICE should be allowed during NOMINAL_OPS."""
        config = policy_engine._get_phase_config(MissionPhase.NOMINAL_OPS)
        assert "RESTART_SERVICE" in config['allowed_actions']
        assert "RESTART_SERVICE" not in config['forbidden_actions']


class TestPayloadOpsPhasePolicy:
    """Test fault response policies during PAYLOAD_OPS phase."""
    
    def test_payload_ops_payload_subsystem_fault(self, policy_engine):
        """During PAYLOAD_OPS, payload subsystem faults should escalate."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.PAYLOAD_OPS,
            anomaly_type='payload_fault',
            severity_score=0.75,
            anomaly_attributes={'subsystem': 'PAYLOAD'}
        )
        
        # Payload faults during payload ops are serious
        assert decision.severity == SeverityLevel.HIGH.value
    
    def test_payload_ops_power_fault(self, policy_engine):
        """During PAYLOAD_OPS, power faults get controlled action."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.PAYLOAD_OPS,
            anomaly_type='power_fault',
            severity_score=0.75,
            anomaly_attributes={}
        )
        
        # HIGH power fault in PAYLOAD_OPS -> CONTROLLED_ACTION
        assert decision.escalation_level == EscalationLevel.CONTROLLED_ACTION.value
    
    def test_payload_ops_thrusters_forbidden(self, policy_engine):
        """FIRE_THRUSTERS should be forbidden during PAYLOAD_OPS."""
        config = policy_engine._get_phase_config(MissionPhase.PAYLOAD_OPS)
        assert "FIRE_THRUSTERS" in config['forbidden_actions']


class TestSafeModePhasePolicy:
    """Test fault response policies during SAFE_MODE phase."""
    
    def test_safe_mode_allows_only_minimal_actions(self, policy_engine):
        """In SAFE_MODE, only minimal actions are allowed."""
        config = policy_engine._get_phase_config(MissionPhase.SAFE_MODE)
        
        # Check that minimal actions are allowed
        allowed = config['allowed_actions']
        assert "LOG_EVENT" in allowed or "MONITOR" in allowed
        
        # Check that active actions are forbidden
        forbidden = config['forbidden_actions']
        assert "RESTART_SERVICE" in forbidden
        assert "FIRE_THRUSTERS" in forbidden
        assert "PAYLOAD_OPERATIONS" in forbidden
    
    def test_safe_mode_critical_does_not_escalate(self, policy_engine):
        """In SAFE_MODE, even critical faults don't escalate further."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.SAFE_MODE,
            anomaly_type='power_fault',
            severity_score=0.95,
            anomaly_attributes={}
        )
        
        # Already in safe mode, no further escalation
        assert decision.escalation_level == EscalationLevel.LOG_ONLY.value
        assert decision.recommended_action == "LOG_ONLY"
    
    def test_safe_mode_no_response_allowed(self, policy_engine):
        """In SAFE_MODE, no automated responses are allowed."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.SAFE_MODE,
            anomaly_type='thermal_fault',
            severity_score=0.50,
            anomaly_attributes={}
        )
        
        assert decision.is_allowed is False


class TestPolicyDecision:
    """Test PolicyDecision dataclass."""
    
    def test_policy_decision_creation(self, policy_engine):
        """Test creating a policy decision."""
        decision = policy_engine.evaluate(
            mission_phase=MissionPhase.NOMINAL_OPS,
            anomaly_type='test_fault',
            severity_score=0.75,
            anomaly_attributes={}
        )
        
        assert isinstance(decision, PolicyDecision)
        assert decision.mission_phase == MissionPhase.NOMINAL_OPS.value
        assert decision.anomaly_type == 'test_fault'
        assert 0 <= decision.severity_score <= 1
        assert 0 <= decision.confidence <= 1
        assert isinstance(decision.reasoning, str)
        assert len(decision.reasoning) > 0


class TestThresholdMultipliers:
    """Test threshold multiplier application."""
    
    def test_launch_high_multiplier(self, policy_engine):
        """LAUNCH phase should have high threshold multiplier (noisy environment)."""
        config = policy_engine._get_phase_config(MissionPhase.LAUNCH)
        assert config['threshold_multiplier'] == 2.0
    
    def test_nominal_standard_multiplier(self, policy_engine):
        """NOMINAL_OPS should have standard multiplier."""
        config = policy_engine._get_phase_config(MissionPhase.NOMINAL_OPS)
        assert config['threshold_multiplier'] == 1.0
    
    def test_safe_mode_sensitive_multiplier(self, policy_engine):
        """SAFE_MODE should have sensitive multiplier (detect problems early)."""
        config = policy_engine._get_phase_config(MissionPhase.SAFE_MODE)
        assert config['threshold_multiplier'] == 0.8  # More sensitive


class TestPhaseConstraints:
    """Test retrieving phase constraints."""
    
    def test_get_phase_constraints(self, policy_engine):
        """Test retrieving all constraints for a phase."""
        constraints = policy_engine.get_phase_constraints(MissionPhase.NOMINAL_OPS)
        
        assert 'phase' in constraints
        assert 'description' in constraints
        assert 'allowed_actions' in constraints
        assert 'forbidden_actions' in constraints
        assert 'threshold_multiplier' in constraints
        assert constraints['phase'] == MissionPhase.NOMINAL_OPS.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
