import yaml
import os
from typing import Dict, Any


class PolicyManager:
    def __init__(self, config_path: str = "config/mission_policies.yaml"):
        self.policies = self._load_policies(config_path)

    def _load_policies(self, path: str) -> Dict[str, Any]:
        """Load policies from YAML file with environment variable substitution."""
        if not os.path.exists(path):
            # Fallback if config not found (e.g. running from different root)
            alt_path = os.path.join(
                os.path.dirname(__file__), "..", "config", "mission_policies.yaml"
            )
            if os.path.exists(alt_path):
                path = alt_path
            else:
                print(f"Warning: Policy config not found at {path}. Using defaults.")
                return {}

        from config.config_utils import load_yaml_config
        return load_yaml_config(path).get("phases", {})

    def get_phase_config(self, phase_name: str) -> Dict[str, Any]:
        """Get configuration for a specific phase."""
        return self.policies.get(phase_name, {})

    def is_action_allowed(self, phase_name: str, action: str) -> bool:
        """Check if an action is allowed in the current phase."""
        config = self.get_phase_config(phase_name)
        if not config:
            return False  # Fail-secure: default deny missing policies

        allowed = config.get("allowed_actions", [])
        forbidden = config.get("forbidden_actions", [])

        # If forbidden explicitly
        if action in forbidden:
            return False

        # If allowed list is present, it must be in there.
        # But 'allowed_actions' might be subset of all actions.
        # Let's assume if 'allowed_actions' exists, it is a whitelist.
        if allowed:
            return action in allowed

        return True

    def get_threshold_multiplier(self, phase_name: str) -> float:
        """Get the sensitivity multiplier for the phase."""
        return self.get_phase_config(phase_name).get("threshold_multiplier", 1.0)
