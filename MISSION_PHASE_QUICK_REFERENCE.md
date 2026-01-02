# Mission-Phase Aware Fault Response - Quick Reference

## Phases at a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CUBESAT MISSION LIFECYCLE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  LAUNCH ──→ DEPLOYMENT ──→ NOMINAL_OPS ──→ PAYLOAD_OPS ─┐          │
│    │           │             │              │            │          │
│    │           │             └──────────────┴────────────┤          │
│    │           │                                          │          │
│    └───────────┴──────────────────────────────────────────┴──→ SAFE_MODE
│                                                                       │
│    ↑ Can recovery from SAFE_MODE to earlier phases                  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Phase Constraints Summary

| Phase | Duration | Tolerance | Response Style | Key Rule |
|-------|----------|-----------|----------------|----------|
| **LAUNCH** | Minutes | Very High (2.0x) | Log-only | Avoid destabilization |
| **DEPLOYMENT** | Hours | High (1.5x) | Alert operators | Limited automation |
| **NOMINAL_OPS** | Days/Weeks | Standard (1.0x) | Full automation | Maximize resilience |
| **PAYLOAD_OPS** | Variable | Standard (1.0x) | Balanced | Protect science data |
| **SAFE_MODE** | Hours/Days | Very Low (0.8x) | Minimal | Survive & communicate |

## Quick Decision Reference

### For a High-Severity Fault (0.75)

```
LAUNCH:       ALERT_OPERATORS (blocked response)
DEPLOYMENT:   ALERT_OPERATORS (blocked response)  
NOMINAL_OPS:  THERMAL_REGULATION or POWER_LOAD_BALANCING
PAYLOAD_OPS:  Depends on subsystem affected
SAFE_MODE:    LOG_ONLY
```

### For a Critical Fault (0.95)

```
ALL PHASES:   → ESCALATE_TO_SAFE_MODE
Exception: Already in SAFE_MODE → LOG_ONLY
```

### For a Recurrent Fault

```
Recurrence >= 3 in 1 hour → ESCALATE_TO_SAFE_MODE (any phase except SAFE_MODE)
```

## Code Examples

### Check Current Phase

```python
from state_machine.state_engine import StateMachine, MissionPhase

sm = StateMachine()
current_phase = sm.get_current_phase()
print(f"Current phase: {current_phase.value}")
```

### Transition Phases

```python
# Valid transitions only
sm.set_phase(MissionPhase.DEPLOYMENT)  # If in LAUNCH
sm.set_phase(MissionPhase.NOMINAL_OPS) # If in DEPLOYMENT

# Emergency: Force SAFE_MODE (always allowed)
sm.force_safe_mode()
```

### Handle Anomaly with Phase Awareness

```python
from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler
from config.mission_phase_policy_loader import MissionPhasePolicyLoader

loader = MissionPhasePolicyLoader()
handler = PhaseAwareAnomalyHandler(sm, loader)

decision = handler.handle_anomaly(
    anomaly_type='power_fault',
    severity_score=0.75,
    confidence=0.85
)

print(decision['recommended_action'])
print(decision['reasoning'])
```

### Get Phase Constraints

```python
constraints = handler.get_phase_constraints(MissionPhase.NOMINAL_OPS)
print(f"Allowed: {constraints['allowed_actions']}")
print(f"Forbidden: {constraints['forbidden_actions']}")
```

## Configuration File Locations

```
config/mission_phase_response_policy.yaml  ← Main policy file
config/mission_phase_policy_loader.py      ← Loader/validator
state_machine/mission_phase_policy_engine.py ← Policy evaluation engine
```

## Testing

```bash
# Quick validation
python test_mission_phase_system.py

# Run unit tests (requires pytest)
pytest tests/test_mission_phase_policy_engine.py -v

# Run integration tests
pytest tests/test_phase_aware_anomaly_flow.py -v

# Dashboard
streamlit run dashboard/app.py
```

## Environment Variables

```bash
# Enable simulation mode (phase switching via UI)
export ASTRAGUARD_SIMULATION_MODE=true
```

## Common Tasks

### Add New Anomaly Type

1. Edit `config/mission_phase_response_policy.yaml`
2. Add to allowed_actions in relevant phases
3. Define severity thresholds
4. Test: `python test_mission_phase_system.py`

### Modify Phase Policy

1. Edit `config/mission_phase_response_policy.yaml`
2. Adjust threshold_multiplier, allowed_actions, or severity_thresholds
3. Validate with test script
4. Deploy (no restart needed - hot-reloadable)

### Debug Anomaly Decision

```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Handle anomaly - will see decision traces
decision = handler.handle_anomaly(anomaly_type, severity, confidence)
print(decision['reasoning'])
```

## Key Files

| File | Purpose |
|------|---------|
| `state_machine/state_engine.py` | Mission phase model & state transitions |
| `state_machine/mission_phase_policy_engine.py` | Policy evaluation logic |
| `config/mission_phase_response_policy.yaml` | Phase policy definitions |
| `config/mission_phase_policy_loader.py` | Policy parser & validator |
| `anomaly_agent/phase_aware_handler.py` | Anomaly-policy integration |
| `dashboard/app.py` | Phase-aware UI |
| `tests/test_*.py` | Unit & integration tests |

## Architecture

```
Telemetry Stream
       ↓
Anomaly Detector (severity, type, confidence)
       ↓
Phase-Aware Handler ──→ State Machine (get current phase)
       ↓
Policy Engine ──→ Policy Loader ──→ YAML Config
       ↓
Decision (action, reasoning, escalation)
       ↓
Response Orchestrator / Dashboard
```

## Performance

- Policy evaluation: < 5ms
- Recurrence check: O(1)
- Memory per anomaly: ~100 bytes
- Config reload: < 100ms

## Support & Documentation

- **TECHNICAL.md** - Detailed technical documentation
- **CONTRIBUTING.md** - Contributor guidelines
- **README.md** - Project overview
- **MISSION_PHASE_IMPLEMENTATION.md** - Full implementation details

---

**Last Updated:** January 2, 2026  
**Version:** 1.0.0  
**Status:** Production Ready
