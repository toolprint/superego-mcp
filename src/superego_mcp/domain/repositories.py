"""Repository interfaces for domain persistence."""

from abc import ABC, abstractmethod

from .models import SecurityRule


class RuleRepository(ABC):
    """Abstract repository for managing security rules."""

    @abstractmethod
    def get_all_rules(self) -> list[SecurityRule]:
        """Get all rules from the repository.

        Returns:
            List of all security rules
        """
        pass

    @abstractmethod
    def get_active_rules(self) -> list[SecurityRule]:
        """Get all active rules from the repository.

        Returns:
            List of active security rules
        """
        pass

    @abstractmethod
    def get_rule_by_id(self, rule_id: str) -> SecurityRule | None:
        """Get a specific rule by its ID.

        Args:
            rule_id: The rule identifier

        Returns:
            The rule if found, None otherwise
        """
        pass

    @abstractmethod
    def add_rule(self, rule: SecurityRule) -> None:
        """Add a new rule to the repository.

        Args:
            rule: The rule to add
        """
        pass

    @abstractmethod
    def update_rule(self, rule: SecurityRule) -> None:
        """Update an existing rule in the repository.

        Args:
            rule: The rule to update
        """
        pass

    @abstractmethod
    def delete_rule(self, rule_id: str) -> None:
        """Delete a rule from the repository.

        Args:
            rule_id: The ID of the rule to delete
        """
        pass

    @abstractmethod
    def reload_rules(self) -> None:
        """Reload rules from the underlying data source."""
        pass
