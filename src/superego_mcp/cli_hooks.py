#!/usr/bin/env python3
"""
Claude Code hooks management for Superego MCP.

This module provides functionality to manage Claude Code hooks in the
~/.claude/settings.json file, allowing users to add, list, and remove
superego-managed hooks safely without disrupting other configurations.
"""

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field


class HooksError(Exception):
    """Base exception for hooks operations."""
    pass


class SettingsNotFoundError(HooksError):
    """Claude settings file not found."""
    pass


class HookNotFoundError(HooksError):
    """Specified hook not found."""
    pass


class InvalidSettingsError(HooksError):
    """Settings file is invalid or corrupted."""
    pass


class SuperegoHook(BaseModel):
    """Represents a superego-managed Claude Code hook."""
    
    id: str = Field(..., description="Unique identifier for the hook")
    matcher: str = Field(..., description="Tool pattern matcher (e.g., '*', 'Bash|Write')")
    event_type: str = Field(default="PreToolUse", description="Hook event type")
    command: str = Field(default="superego advise", description="Command to execute")
    timeout: int = Field(default=5000, description="Timeout in milliseconds")
    enabled: bool = Field(default=True, description="Whether the hook is enabled")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_claude_hook(self) -> Dict[str, Any]:
        """Convert to Claude Code hook format."""
        return {
            "type": "command",
            "command": self.command,
            "timeout": self.timeout,
            "_superego_managed": True,
            "_superego_id": self.id,
            "_superego_created": self.created_at.isoformat(),
            "_superego_enabled": self.enabled,
            "_superego_matcher": self.matcher,
            "_superego_event_type": self.event_type
        }
    
    @classmethod
    def from_claude_hook(cls, hook_data: Dict[str, Any], matcher: str, event_type: str = "PreToolUse") -> "SuperegoHook":
        """Create SuperegoHook from Claude Code hook data."""
        return cls(
            id=hook_data.get("_superego_id", str(uuid.uuid4())),
            matcher=hook_data.get("_superego_matcher", matcher),
            event_type=hook_data.get("_superego_event_type", event_type),
            command=hook_data.get("command", "superego advise"),
            timeout=hook_data.get("timeout", 5000),
            enabled=hook_data.get("_superego_enabled", True),
            created_at=datetime.fromisoformat(hook_data.get("_superego_created", datetime.now(timezone.utc).isoformat()))
        )


class ClaudeSettingsManager:
    """Manages Claude Code settings.json file operations."""
    
    def __init__(self, settings_path: Optional[Path] = None):
        """Initialize the settings manager.
        
        Args:
            settings_path: Optional custom path to settings file
        """
        self.settings_path = settings_path or (Path.home() / ".claude" / "settings.json")
        self.logger = structlog.get_logger("claude_settings")
    
    def read_settings(self) -> Dict[str, Any]:
        """Read Claude Code settings from file.
        
        Returns:
            Dictionary containing settings data
            
        Raises:
            SettingsNotFoundError: If settings file doesn't exist
            InvalidSettingsError: If settings file is invalid JSON
        """
        if not self.settings_path.exists():
            # Create empty settings structure
            return {"hooks": {}}
        
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            # Ensure hooks section exists
            if "hooks" not in settings:
                settings["hooks"] = {}
                
            return settings
            
        except json.JSONDecodeError as e:
            raise InvalidSettingsError(f"Invalid JSON in settings file: {e}")
        except Exception as e:
            raise InvalidSettingsError(f"Failed to read settings file: {e}")
    
    def write_settings(self, settings: Dict[str, Any], create_backup: bool = True) -> None:
        """Write settings to file safely.
        
        Args:
            settings: Settings data to write
            create_backup: Whether to create a backup of existing file
            
        Raises:
            InvalidSettingsError: If settings data is invalid
        """
        # Ensure directory exists
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create backup if file exists and backup is requested
        if create_backup and self.settings_path.exists():
            backup_path = self.settings_path.with_suffix(
                f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            shutil.copy2(self.settings_path, backup_path)
            self.logger.info("Created settings backup", backup_path=str(backup_path))
        
        # Write to temporary file first
        temp_path = self.settings_path.with_suffix(".tmp")
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            
            # Validate by reading back
            with open(temp_path, 'r', encoding='utf-8') as f:
                json.load(f)
            
            # Move into place atomically
            temp_path.replace(self.settings_path)
            self.logger.info("Settings updated successfully")
            
        except Exception as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise InvalidSettingsError(f"Failed to write settings: {e}")


class HooksManager:
    """Main hooks management logic."""
    
    # Common matcher patterns
    DEFAULT_MATCHERS = {
        "all": "*",
        "common": "Bash|Write|Edit|MultiEdit",
        "dangerous": "Bash|Write|Edit|MultiEdit",
        "filesystem": "Write|Edit|MultiEdit|Read",
        "mcp": "mcp__.*"
    }
    
    def __init__(self, settings_path: Optional[Path] = None):
        """Initialize the hooks manager.
        
        Args:
            settings_path: Optional custom path to settings file
        """
        self.settings_manager = ClaudeSettingsManager(settings_path)
        self.logger = structlog.get_logger("hooks_manager")
    
    def add_hook(self, matcher: str = "*", event_type: str = "PreToolUse", 
                 command: str = "superego advise", timeout: int = 5000) -> SuperegoHook:
        """Add a new superego hook.
        
        Args:
            matcher: Tool pattern matcher
            event_type: Hook event type
            command: Command to execute
            timeout: Timeout in milliseconds
            
        Returns:
            Created SuperegoHook instance
            
        Raises:
            InvalidSettingsError: If settings operations fail
        """
        # Create new hook
        hook = SuperegoHook(
            id=str(uuid.uuid4()),
            matcher=matcher,
            event_type=event_type,
            command=command,
            timeout=timeout
        )
        
        # Read current settings
        settings = self.settings_manager.read_settings()
        
        # Ensure event type section exists
        if event_type not in settings["hooks"]:
            settings["hooks"][event_type] = []
        
        # Find existing matcher group or create new one
        matcher_group = None
        for group in settings["hooks"][event_type]:
            if group.get("matcher") == matcher:
                matcher_group = group
                break
        
        if matcher_group is None:
            # Create new matcher group
            matcher_group = {
                "matcher": matcher,
                "hooks": []
            }
            settings["hooks"][event_type].append(matcher_group)
        
        # Add hook to the group
        claude_hook = hook.to_claude_hook()
        matcher_group["hooks"].append(claude_hook)
        
        # Write settings
        self.settings_manager.write_settings(settings)
        
        self.logger.info("Added superego hook", 
                        hook_id=hook.id, matcher=matcher, event_type=event_type)
        
        return hook
    
    def list_hooks(self, event_type: Optional[str] = None) -> List[SuperegoHook]:
        """List all superego-managed hooks.
        
        Args:
            event_type: Optional filter by event type
            
        Returns:
            List of SuperegoHook instances
        """
        settings = self.settings_manager.read_settings()
        hooks = []
        
        for event_name, event_hooks in settings["hooks"].items():
            # Filter by event type if specified
            if event_type and event_name != event_type:
                continue
                
            for matcher_group in event_hooks:
                matcher = matcher_group.get("matcher", "*")
                
                for hook_data in matcher_group.get("hooks", []):
                    # Only include superego-managed hooks
                    if hook_data.get("_superego_managed"):
                        hook = SuperegoHook.from_claude_hook(hook_data, matcher, event_name)
                        hooks.append(hook)
        
        return hooks
    
    def remove_hook(self, hook_id: Optional[str] = None, matcher: Optional[str] = None) -> int:
        """Remove superego hooks.
        
        Args:
            hook_id: Specific hook ID to remove
            matcher: Remove all hooks with this matcher
            
        Returns:
            Number of hooks removed
            
        Raises:
            HookNotFoundError: If no matching hooks found
            ValueError: If neither hook_id nor matcher provided
        """
        if not hook_id and not matcher:
            raise ValueError("Either hook_id or matcher must be provided")
        
        settings = self.settings_manager.read_settings()
        removed_count = 0
        
        for event_name, event_hooks in settings["hooks"].items():
            # Process each matcher group
            for matcher_group in event_hooks[:]:  # Copy list to allow modification
                group_hooks = matcher_group.get("hooks", [])
                original_count = len(group_hooks)
                
                # Filter out superego hooks to remove
                remaining_hooks = []
                for hook_data in group_hooks:
                    should_remove = False
                    
                    if hook_data.get("_superego_managed"):
                        if hook_id and hook_data.get("_superego_id") == hook_id:
                            should_remove = True
                        elif matcher and matcher_group.get("matcher") == matcher:
                            should_remove = True
                    
                    if not should_remove:
                        remaining_hooks.append(hook_data)
                    else:
                        removed_count += 1
                        self.logger.info("Removed superego hook", 
                                       hook_id=hook_data.get("_superego_id"),
                                       matcher=matcher_group.get("matcher"))
                
                # Update hooks list
                matcher_group["hooks"] = remaining_hooks
                
                # Remove empty matcher groups (only if all hooks were superego-managed)
                if not remaining_hooks and original_count > 0:
                    # Check if all original hooks were superego-managed
                    all_superego = all(h.get("_superego_managed") for h in group_hooks)
                    if all_superego:
                        event_hooks.remove(matcher_group)
        
        if removed_count == 0:
            if hook_id:
                raise HookNotFoundError(f"Hook with ID {hook_id} not found")
            else:
                raise HookNotFoundError(f"No hooks found with matcher '{matcher}'")
        
        # Write updated settings
        self.settings_manager.write_settings(settings)
        
        return removed_count
    
    def get_hook(self, hook_id: str) -> Optional[SuperegoHook]:
        """Get a specific hook by ID.
        
        Args:
            hook_id: Hook ID to find
            
        Returns:
            SuperegoHook instance or None if not found
        """
        hooks = self.list_hooks()
        for hook in hooks:
            if hook.id == hook_id:
                return hook
        return None
    
    def validate_claude_installation(self) -> bool:
        """Check if Claude Code is installed and settings directory exists.
        
        Returns:
            True if Claude Code appears to be installed
        """
        claude_dir = Path.home() / ".claude"
        return claude_dir.exists() and claude_dir.is_dir()