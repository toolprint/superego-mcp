"""Infrastructure implementations of domain repositories."""

import os
from pathlib import Path
from typing import Any

import yaml
from watchfiles import awatch

from superego_mcp.domain.models import SecurityRule
from superego_mcp.domain.repositories import RuleRepository


def is_ci_environment() -> bool:
    """Detect if running in a CI environment.

    Returns:
        True if running in CI (GitHub Actions, GitLab CI, etc.), False otherwise
    """
    return any(
        [
            os.getenv("CI"),
            os.getenv("GITHUB_ACTIONS"),
            os.getenv("GITLAB_CI"),
            os.getenv("JENKINS_URL"),
            os.getenv("BUILDKITE"),
            os.getenv("CIRCLECI"),
        ]
    )


class YamlRuleRepository(RuleRepository):
    """YAML file-based implementation of RuleRepository."""

    def __init__(self, rules_file_path: str):
        """Initialize the YAML rule repository.

        Args:
            rules_file_path: Path to the YAML rules file
        """
        self.rules_file_path = Path(rules_file_path)
        self._rules_cache: dict[str, SecurityRule] = {}
        self._load_rules()

    def _load_rules(self) -> None:
        """Load rules from the YAML file into the cache."""
        if not self.rules_file_path.exists():
            self._rules_cache = {}
            return

        try:
            with open(self.rules_file_path, encoding="utf-8") as f:
                rules_data = yaml.safe_load(f) or {}

            self._rules_cache = {}
            for rule_data in rules_data.get("rules", []):
                rule = SecurityRule(**rule_data)
                self._rules_cache[rule.id] = rule

        except (yaml.YAMLError, ValueError) as e:
            raise ValueError(
                f"Failed to load rules from {self.rules_file_path}: {e}"
            ) from e

    def get_all_rules(self) -> list[SecurityRule]:
        """Get all rules from the repository."""
        return list(self._rules_cache.values())

    def get_active_rules(self) -> list[SecurityRule]:
        """Get all security rules from the repository."""
        return list(self._rules_cache.values())

    def get_rule_by_id(self, rule_id: str) -> SecurityRule | None:
        """Get a specific rule by its ID."""
        return self._rules_cache.get(rule_id)

    def add_rule(self, rule: SecurityRule) -> None:
        """Add a new rule to the repository."""
        self._rules_cache[rule.id] = rule
        self._save_rules()

    def update_rule(self, rule: SecurityRule) -> None:
        """Update an existing rule in the repository."""
        if rule.id not in self._rules_cache:
            raise ValueError(f"Rule with ID {rule.id} not found")
        self._rules_cache[rule.id] = rule
        self._save_rules()

    def delete_rule(self, rule_id: str) -> None:
        """Delete a rule from the repository."""
        if rule_id not in self._rules_cache:
            raise ValueError(f"Rule with ID {rule_id} not found")
        del self._rules_cache[rule_id]
        self._save_rules()

    def reload_rules(self) -> None:
        """Reload rules from the underlying data source."""
        self._load_rules()

    def _save_rules(self) -> None:
        """Save the current rules cache to the YAML file."""
        # Ensure parent directory exists
        self.rules_file_path.parent.mkdir(parents=True, exist_ok=True)

        rules_data = {
            "rules": [rule.model_dump() for rule in self._rules_cache.values()]
        }

        with open(self.rules_file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(rules_data, f, default_flow_style=False, indent=2)

    async def start_file_watcher(self, callback: Any = None) -> None:
        """Start watching the rules file for changes.

        Args:
            callback: Optional callback to call when file changes
        """
        # In CI environments, ignore permission denied errors to avoid
        # failures with systemd private directories and other restricted paths
        ignore_perms = is_ci_environment()

        # Watch the rules file for changes using async iterator
        async for _changes in awatch(
            str(self.rules_file_path), ignore_permission_denied=ignore_perms
        ):
            self.reload_rules()
            if callback:
                await callback()
