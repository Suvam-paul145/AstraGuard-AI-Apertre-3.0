# Contributing to AstraGuard AI for ECWoC '26

Welcome to the AstraGuard AI project! We are thrilled to have you as part of Elite Coders Winter of Code '26.

## 👥 Contributor Roles & Focus Areas

We are looking for contributions in specific areas. Please identify your role and focus on relevant issues:

### 🎨 Frontend (React / Streamlit)
- **Focus**: Integrating the dashboard with the API, enhancing UI/UX, and visualizing real-time threat data.
- **Requirements**: Clean component structure, responsive design, and proper state management.
- **Mission-Phase Awareness**: When adding new UI elements for anomaly response, consider the mission phase constraints. Ensure the dashboard shows which actions are available/forbidden in the current phase.

### ⚙️ Backend (Node.js / FastAPI / Python)
- **Focus**: API development, data aggregation, authentication, and connecting the AI engine to the frontend.
- **Requirements**: Efficient endpoints, proper error handling, and comprehensive API documentation.
- **Mission-Phase Awareness**: When adding new anomaly detection or response logic, integrate it with the mission-phase policy engine (see `state_machine/mission_phase_policy_engine.py`). Your anomaly type should be evaluated against the current mission phase.

### 🛡️ Security Engine & Anomaly Detection (Python)
- **Focus**: Enhancing the anomaly detection logic, adding new fault classifiers, and improving the memory engine.
- **Requirements**: Security-first mindset, modular code, and rigorous testing.
- **Mission-Phase Awareness**: New anomaly types must be integrated into the policy system. Update `config/mission_phase_response_policy.yaml` with severity thresholds and escalation rules for your new anomaly type across all mission phases.

### 📋 Policy & Configuration (YAML)
- **Focus**: Defining and refining mission-phase policies, threat severity thresholds, and response escalation rules.
- **Requirements**: Clear documentation, realistic CubeSat constraints, and validation against test scenarios.
- **Key Files**:
  - `config/mission_phase_response_policy.yaml` - Main policy configuration
  - `config/mission_phase_policy_loader.py` - Policy parser and validator

## Understanding Mission Phases

AstraGuard now operates with **mission-phase awareness**. Before contributing, understand the five mission phases:

| Phase | Purpose | Key Constraint | Response Style |
|-------|---------|-----------------|-----------------|
| **LAUNCH** | Rocket ascent | Minimize disruption | Log-only |
| **DEPLOYMENT** | System stabilization | Avoid aggressive recovery | Alert operators |
| **NOMINAL_OPS** | Standard mission | Maximize reliability | Full automation |
| **PAYLOAD_OPS** | Science mission | Protect mission data | Balanced |
| **SAFE_MODE** | Survival mode | Minimal power draw | Passive monitoring |

**When adding new features:**
1. Identify which phases your feature affects
2. Update the policy config with appropriate thresholds and actions
3. Add tests covering at least LAUNCH, NOMINAL_OPS, and SAFE_MODE phases
4. Document the phase-specific behavior in your PR description

## 🚫 What We Do NOT Accept
- **Random PRs for streaks**: Submissions that just fix a typo or add a comment solely to keep a GitHub streak alive will be closed.
- **Unscoped work**: Please do not start working on a massive feature without discussing it in an issue first.
- **Low-quality code**: Code without types, tests, or documentation will not be merged.

## 📝 How to Contribute

1.  **Find an Issue**: Look for issues tagged with your role (e.g., `role:frontend`, `role:security`).
2.  **Claim the Issue**: Comment on the issue to let us know you are working on it.
3.  **Fork & Branch**: 
    ```bash
    git checkout -b feature/issue-id-short-description
    ```
4.  **Implement**: Write clean, tested code.
5.  **Submit PR**: detailed description of your changes.

## 🧪 Testing Guidelines
- Run existing tests before submitting.
- Add new tests for any new logic.
- Ensure the linter is happy (we use `black` for Python and `eslint` for JS).

## 📜 Code of Conduct
Be respectful, constructive, and inclusive. We are all here to learn and build something awesome together.

Happy Coding! 🚀
