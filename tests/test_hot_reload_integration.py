"""Integration tests for the complete hot-reload functionality."""

import asyncio
import tempfile
from pathlib import Path

import pytest
import yaml

from superego_mcp.domain.models import ToolRequest
from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.infrastructure.config_watcher import ConfigWatcher
from superego_mcp.infrastructure.error_handler import HealthMonitor


class TestHotReloadIntegration:
    """Integration test suite for complete hot-reload functionality."""

    @pytest.fixture
    def initial_rules_data(self):
        """Initial rules data for testing."""
        return {
            "rules": [
                {
                    "id": "block_rm",
                    "priority": 1,
                    "conditions": {"tool_name": "rm"},
                    "action": "deny",
                    "reason": "Dangerous command blocked"
                },
                {
                    "id": "allow_read",
                    "priority": 10,
                    "conditions": {"tool_name": ["read", "cat"]},
                    "action": "allow",
                    "reason": "Safe read operations"
                }
            ]
        }

    @pytest.fixture
    async def temp_rules_file(self, initial_rules_data):
        """Create a temporary rules file for integration testing."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            yaml.dump(initial_rules_data, f)
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    @pytest.fixture
    def health_monitor(self):
        """Create a HealthMonitor for integration testing."""
        return HealthMonitor()

    @pytest.fixture
    async def integrated_system(self, temp_rules_file, health_monitor):
        """Set up the complete integrated system."""
        # Create security policy engine
        security_policy = SecurityPolicyEngine(temp_rules_file, health_monitor)
        
        # Create config watcher
        config_watcher = ConfigWatcher(
            watch_path=temp_rules_file,
            reload_callback=security_policy.reload_rules,
            debounce_seconds=0.1,  # Short debounce for testing
        )
        
        # Register components with health monitor
        health_monitor.register_component("security_policy", security_policy)
        health_monitor.register_component("config_watcher", config_watcher)
        
        # Start the config watcher
        await config_watcher.start()
        
        yield {
            "security_policy": security_policy,
            "config_watcher": config_watcher,
            "health_monitor": health_monitor,
            "rules_file": temp_rules_file,
        }
        
        # Cleanup
        await config_watcher.stop()

    @pytest.mark.integration
    async def test_end_to_end_hot_reload(self, integrated_system):
        """Test complete end-to-end hot-reload functionality."""
        security_policy = integrated_system["security_policy"]
        rules_file = integrated_system["rules_file"]
        
        # Test initial behavior
        rm_request = ToolRequest(
            tool_name="rm",
            parameters={"path": "/test/file"},
            cwd="/test",
            session_id="test-session",
            agent_id="test-agent"
        )
        
        initial_decision = await security_policy.evaluate(rm_request)
        assert initial_decision.action == "deny"
        assert initial_decision.rule_id == "block_rm"
        
        # Update rules to allow rm
        new_rules_data = {
            "rules": [
                {
                    "id": "allow_rm_now",
                    "priority": 1,
                    "conditions": {"tool_name": "rm"},
                    "action": "allow",
                    "reason": "Now allowed after policy change"
                },
                {
                    "id": "allow_read",
                    "priority": 10,
                    "conditions": {"tool_name": ["read", "cat"]},
                    "action": "allow",
                    "reason": "Safe read operations"
                }
            ]
        }
        
        # Write new rules to file
        with open(rules_file, 'w') as f:
            yaml.dump(new_rules_data, f)
        
        # Wait for file system event processing and reload
        await asyncio.sleep(0.5)
        
        # Test updated behavior
        updated_decision = await security_policy.evaluate(rm_request)
        assert updated_decision.action == "allow"
        assert updated_decision.rule_id == "allow_rm_now"
        
        # Verify rules count updated
        rules_count = await security_policy.get_rules_count()
        assert rules_count == 2

    @pytest.mark.integration
    async def test_hot_reload_with_invalid_config_recovery(self, integrated_system):
        """Test recovery from invalid configuration during hot-reload."""
        security_policy = integrated_system["security_policy"]
        health_monitor = integrated_system["health_monitor"]
        rules_file = integrated_system["rules_file"]
        
        # Verify initial state
        initial_count = await security_policy.get_rules_count()
        assert initial_count == 2
        
        # Write invalid YAML to trigger reload failure
        with open(rules_file, 'w') as f:
            f.write("invalid: yaml: [content")
        
        # Wait for file system event and processing
        await asyncio.sleep(0.5)
        
        # System should have restored from backup
        recovered_count = await security_policy.get_rules_count()
        assert recovered_count == initial_count  # Should be restored
        
        # Health monitor should show the failure
        assert health_monitor._config_reload_metrics["failed_reloads"] > 0
        assert health_monitor._config_reload_metrics["last_reload_success"] is False
        
        # System should still be functional
        test_request = ToolRequest(
            tool_name="read",
            parameters={},
            cwd="/test",
            session_id="test-session",
            agent_id="test-agent"
        )
        
        decision = await security_policy.evaluate(test_request)
        assert decision.action == "allow"

    @pytest.mark.integration
    async def test_concurrent_operations_during_reload(self, integrated_system):
        """Test concurrent operations during configuration reload."""
        security_policy = integrated_system["security_policy"]
        rules_file = integrated_system["rules_file"]
        
        test_request = ToolRequest(
            tool_name="read",
            parameters={},
            cwd="/test",
            session_id="test-session",
            agent_id="test-agent"
        )
        
        async def continuous_evaluation():
            """Continuously evaluate requests during reload."""
            results = []
            for i in range(20):
                try:
                    decision = await security_policy.evaluate(test_request)
                    results.append(decision.action)
                    await asyncio.sleep(0.01)
                except Exception as e:
                    results.append(f"error: {e}")
            return results
        
        async def trigger_reload():
            """Trigger configuration reload."""
            await asyncio.sleep(0.05)  # Let evaluation start
            
            new_rules = {
                "rules": [
                    {
                        "id": "updated_read_rule",
                        "priority": 1,
                        "conditions": {"tool_name": "read"},
                        "action": "allow",
                        "reason": "Updated during concurrent test"
                    }
                ]
            }
            
            with open(rules_file, 'w') as f:
                yaml.dump(new_rules, f)
            
            await asyncio.sleep(0.15)  # Wait for reload processing
        
        # Run both tasks concurrently
        eval_task = asyncio.create_task(continuous_evaluation())
        reload_task = asyncio.create_task(trigger_reload())
        
        results, _ = await asyncio.gather(eval_task, reload_task)
        
        # Should complete without deadlock and have mostly successful evaluations
        successful_results = [r for r in results if r == "allow"]
        assert len(successful_results) >= 15  # Most evaluations should succeed

    @pytest.mark.integration
    async def test_health_monitoring_during_hot_reload(self, integrated_system):
        """Test health monitoring during hot-reload operations."""
        security_policy = integrated_system["security_policy"]
        config_watcher = integrated_system["config_watcher"]
        health_monitor = integrated_system["health_monitor"]
        rules_file = integrated_system["rules_file"]
        
        # Check initial health
        initial_health = await health_monitor.check_health()
        assert initial_health.status == "healthy"
        assert "security_policy" in initial_health.components
        assert "config_watcher" in initial_health.components
        
        # Perform successful reload
        new_rules = {
            "rules": [
                {
                    "id": "health_test_rule",
                    "priority": 1,
                    "conditions": {"tool_name": "health_test"},
                    "action": "sample",
                    "reason": "Testing health monitoring"
                }
            ]
        }
        
        with open(rules_file, 'w') as f:
            yaml.dump(new_rules, f)
        
        await asyncio.sleep(0.5)  # Wait for reload
        
        # Check health after successful reload
        post_reload_health = await health_monitor.check_health()
        assert post_reload_health.status == "healthy"
        
        # Verify reload metrics were updated
        config_metrics = post_reload_health.metrics["config_reload_metrics"]
        assert config_metrics["total_reloads"] >= 1
        assert config_metrics["successful_reloads"] >= 1
        assert config_metrics["last_reload_success"] is True
        
        # Component health checks should show healthy status
        assert post_reload_health.components["security_policy"].status == "healthy"
        assert post_reload_health.components["config_watcher"].status == "healthy"

    @pytest.mark.integration
    async def test_multiple_rapid_file_changes(self, integrated_system):
        """Test handling of multiple rapid file changes (debouncing)."""
        security_policy = integrated_system["security_policy"]
        health_monitor = integrated_system["health_monitor"]
        rules_file = integrated_system["rules_file"]
        
        initial_reload_count = health_monitor._config_reload_metrics["total_reloads"]
        
        # Make multiple rapid changes
        for i in range(5):
            rules_data = {
                "rules": [
                    {
                        "id": f"rapid_change_{i}",
                        "priority": 1,
                        "conditions": {"tool_name": f"tool_{i}"},
                        "action": "allow",
                        "reason": f"Rapid change {i}"
                    }
                ]
            }
            
            with open(rules_file, 'w') as f:
                yaml.dump(rules_data, f)
            
            await asyncio.sleep(0.02)  # Very short delay between changes
        
        # Wait for debouncing and processing
        await asyncio.sleep(1.0)
        
        # Should have consolidated the changes (fewer reloads than file writes due to debouncing)
        final_reload_count = health_monitor._config_reload_metrics["total_reloads"]
        total_new_reloads = final_reload_count - initial_reload_count
        
        # Should be fewer reloads than changes due to debouncing
        assert total_new_reloads < 5
        assert total_new_reloads >= 1  # But at least one reload should have occurred
        
        # Final state should reflect the last change
        final_rules_count = await security_policy.get_rules_count()
        assert final_rules_count == 1
        
        # Get the final rule to verify it's the last one
        rules = security_policy.rules
        assert len(rules) == 1
        assert rules[0].id == "rapid_change_4"

    @pytest.mark.integration
    async def test_graceful_shutdown_during_operations(self, integrated_system):
        """Test graceful shutdown during active operations."""
        security_policy = integrated_system["security_policy"]
        config_watcher = integrated_system["config_watcher"]
        rules_file = integrated_system["rules_file"]
        
        # Start some background operations
        test_request = ToolRequest(
            tool_name="read",
            parameters={},
            cwd="/test",
            session_id="test-session",
            agent_id="test-agent"
        )
        
        async def background_evaluation():
            """Background evaluation task."""
            for _ in range(100):
                try:
                    await security_policy.evaluate(test_request)
                    await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass  # Ignore other exceptions during shutdown
        
        # Start background task
        eval_task = asyncio.create_task(background_evaluation())
        
        # Trigger a file change
        new_rules = {
            "rules": [
                {
                    "id": "shutdown_test_rule",
                    "priority": 1,
                    "conditions": {"tool_name": "shutdown_test"},
                    "action": "deny",
                    "reason": "Testing graceful shutdown"
                }
            ]
        }
        
        with open(rules_file, 'w') as f:
            yaml.dump(new_rules, f)
        
        # Wait a bit for operations to start
        await asyncio.sleep(0.1)
        
        # Shutdown the config watcher (this should be graceful)
        await config_watcher.stop()
        
        # Cancel background task
        eval_task.cancel()
        try:
            await eval_task
        except asyncio.CancelledError:
            pass
        
        # Verify watcher is properly stopped
        health = config_watcher.health_check()
        assert health["status"] == "unhealthy"
        assert health["is_running"] is False

    @pytest.mark.integration 
    async def test_file_deletion_and_recreation(self, integrated_system):
        """Test behavior when config file is deleted and recreated."""
        security_policy = integrated_system["security_policy"]
        health_monitor = integrated_system["health_monitor"]
        rules_file = integrated_system["rules_file"]
        
        # Store initial state
        initial_count = await security_policy.get_rules_count()
        
        # Delete the config file
        rules_file.unlink()
        
        # Wait for file system event
        await asyncio.sleep(0.5)
        
        # System should still have backup rules
        count_after_deletion = await security_policy.get_rules_count()
        assert count_after_deletion == initial_count  # Backup should be restored
        
        # ConfigWatcher should handle file deletion gracefully without triggering reload callback
        # (which is correct behavior - no point reloading if file doesn't exist during debounce)
        
        # Recreate the file with new content
        new_rules = {
            "rules": [
                {
                    "id": "recreated_rule",
                    "priority": 1,
                    "conditions": {"tool_name": "recreated"},
                    "action": "sample",
                    "reason": "File was recreated"
                }
            ]
        }
        
        with open(rules_file, 'w') as f:
            yaml.dump(new_rules, f)
        
        # Wait for reload
        await asyncio.sleep(0.5)
        
        # Should now have the new rules
        final_count = await security_policy.get_rules_count()
        assert final_count == 1
        
        rule = await security_policy.get_rule_by_id("recreated_rule")
        assert rule is not None
        assert rule.action.value == "sample"