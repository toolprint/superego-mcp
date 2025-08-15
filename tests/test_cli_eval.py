"""Tests for CLI evaluation functionality."""

import json
from io import StringIO
from unittest.mock import patch

import pytest

from superego_mcp.cli_eval import CLIEvaluator, main
from superego_mcp.domain.claude_code_models import PreToolUseInput
from superego_mcp.infrastructure.inference import MockInferenceProvider


class TestCLIEvaluator:
    """Test cases for CLIEvaluator class."""

    @pytest.fixture
    def evaluator(self):
        """Create a CLIEvaluator instance for testing."""
        return CLIEvaluator()

    @pytest.fixture
    def valid_hook_input(self):
        """Create valid hook input for testing."""
        return {
            "session_id": "test_session",
            "transcript_path": "/tmp/test.json",
            "cwd": "/tmp",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
        }

    @pytest.fixture
    def dangerous_hook_input(self):
        """Create hook input with dangerous command."""
        return {
            "session_id": "test_session",
            "transcript_path": "/tmp/test.json",
            "cwd": "/tmp",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
        }

    def test_evaluator_initialization(self, evaluator):
        """Test that evaluator initializes correctly."""
        assert evaluator.hook_integration is not None
        assert evaluator.mock_provider is not None
        assert evaluator.inference_manager is not None
        assert "mock_inference" in evaluator.inference_manager.providers

    @pytest.mark.asyncio
    async def test_evaluate_safe_command(self, evaluator, valid_hook_input):
        """Test evaluation of a safe command."""
        with patch("sys.stdin", StringIO(json.dumps(valid_hook_input))):
            result = await evaluator.evaluate_from_stdin()

        assert "hookSpecificOutput" in result
        hook_output = result["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PreToolUse"
        assert hook_output["permissionDecision"] == "allow"
        assert "safe" in hook_output["permissionDecisionReason"].lower()

    @pytest.mark.asyncio
    async def test_evaluate_dangerous_command(self, evaluator, dangerous_hook_input):
        """Test evaluation of a dangerous command."""
        with patch("sys.stdin", StringIO(json.dumps(dangerous_hook_input))):
            result = await evaluator.evaluate_from_stdin()

        assert "hookSpecificOutput" in result
        hook_output = result["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PreToolUse"
        assert hook_output["permissionDecision"] == "deny"
        assert "rm -rf" in hook_output["permissionDecisionReason"]

    @pytest.mark.asyncio
    async def test_evaluate_empty_input(self, evaluator):
        """Test evaluation with empty input."""
        with patch("sys.stdin", StringIO("")):
            with pytest.raises(ValueError, match="No input data received"):
                await evaluator.evaluate_from_stdin()

    @pytest.mark.asyncio
    async def test_evaluate_invalid_json(self, evaluator):
        """Test evaluation with invalid JSON."""
        with patch("sys.stdin", StringIO("invalid json")):
            with pytest.raises(ValueError, match="Invalid JSON input"):
                await evaluator.evaluate_from_stdin()

    @pytest.mark.asyncio
    async def test_evaluate_minimal_input(self, evaluator):
        """Test evaluation with minimal input fields."""
        minimal_input = {
            "tool_name": "Write",
            "tool_input": {"file_path": "test.txt", "content": "hello"},
        }

        with patch("sys.stdin", StringIO(json.dumps(minimal_input))):
            result = await evaluator.evaluate_from_stdin()

        assert "hookSpecificOutput" in result
        hook_output = result["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PreToolUse"
        assert hook_output["permissionDecision"] in ["allow", "deny"]

    def test_parse_hook_input_lenient(self, evaluator):
        """Test lenient parsing of hook input."""
        minimal_input = {"tool_name": "Test"}
        result = evaluator._parse_hook_input_lenient(minimal_input)

        assert isinstance(result, PreToolUseInput)
        assert result.tool_name == "Test"
        assert result.session_id == "cli_eval_session"
        assert result.hook_event_name == "PreToolUse"

    def test_convert_to_tool_request(self, evaluator):
        """Test conversion from hook input to tool request."""
        hook_input = PreToolUseInput(
            session_id="test",
            transcript_path="",
            cwd="/tmp",
            hook_event_name="PreToolUse",
            tool_name="Bash",
            tool_input={"command": "echo hello"},
        )

        tool_request = evaluator._convert_to_tool_request(hook_input)

        assert tool_request.tool_name == "Bash"
        assert tool_request.parameters == {"command": "echo hello"}
        assert tool_request.context["session_id"] == "test"
        assert tool_request.context["source"] == "cli_eval"

    @pytest.mark.asyncio
    async def test_protected_path_detection(self, evaluator):
        """Test detection of protected path access."""
        protected_input = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/etc/passwd"},
        }

        with patch("sys.stdin", StringIO(json.dumps(protected_input))):
            result = await evaluator.evaluate_from_stdin()

        hook_output = result["hookSpecificOutput"]
        assert hook_output["permissionDecision"] == "deny"
        assert "/etc/passwd" in hook_output["permissionDecisionReason"]


class TestMockInferenceProvider:
    """Test cases for MockInferenceProvider class."""

    @pytest.fixture
    def provider(self):
        """Create a MockInferenceProvider instance for testing."""
        return MockInferenceProvider()

    @pytest.fixture
    def custom_provider(self):
        """Create a MockInferenceProvider with custom config."""
        config = {
            "dangerous_patterns": ["custom_danger"],
            "protected_paths": ["/custom/path/"],
        }
        return MockInferenceProvider(config)

    @pytest.mark.asyncio
    async def test_provider_initialization(self, provider):
        """Test provider initialization."""
        await provider.initialize()

        info = provider.get_provider_info()
        assert info.name == "mock_inference"
        assert info.type == "mock"
        assert "pattern-matcher-v1" in info.models

    @pytest.mark.asyncio
    async def test_health_check(self, provider):
        """Test provider health check."""
        health = await provider.health_check()

        assert health.healthy is True
        assert "Mock provider operational" in health.message
        assert health.error_count == 0

    @pytest.mark.asyncio
    async def test_evaluate_safe_request(self, provider):
        """Test evaluation of safe request."""
        from superego_mcp.domain.models import ToolRequest
        from superego_mcp.infrastructure.inference import InferenceRequest

        tool_request = ToolRequest(
            tool_name="Write",
            parameters={"file_path": "safe.txt", "content": "hello"},
            context={},
        )

        inference_request = InferenceRequest(
            prompt="Test prompt",
            tool_request=tool_request,
            rule=None,
            cache_key="test",
            timeout_seconds=5,
        )

        decision = await provider.evaluate(inference_request)

        assert decision.decision == "allow"
        assert decision.confidence > 0
        assert decision.provider == "mock_inference"
        assert decision.response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_evaluate_dangerous_request(self, provider):
        """Test evaluation of dangerous request."""
        from superego_mcp.domain.models import ToolRequest
        from superego_mcp.infrastructure.inference import InferenceRequest

        tool_request = ToolRequest(
            tool_name="Bash", parameters={"command": "rm -rf /important"}, context={}
        )

        inference_request = InferenceRequest(
            prompt="Test dangerous prompt",
            tool_request=tool_request,
            rule=None,
            cache_key="test",
            timeout_seconds=5,
        )

        decision = await provider.evaluate(inference_request)

        assert decision.decision == "deny"
        assert decision.confidence > 0.8
        assert "rm -rf" in decision.reasoning
        assert "dangerous_command" in decision.risk_factors

    @pytest.mark.asyncio
    async def test_custom_patterns(self, custom_provider):
        """Test provider with custom patterns."""
        from superego_mcp.domain.models import ToolRequest
        from superego_mcp.infrastructure.inference import InferenceRequest

        tool_request = ToolRequest(
            tool_name="Test", parameters={"data": "custom_danger here"}, context={}
        )

        inference_request = InferenceRequest(
            prompt="Test with custom danger",
            tool_request=tool_request,
            rule=None,
            cache_key="test",
            timeout_seconds=5,
        )

        decision = await custom_provider.evaluate(inference_request)

        assert decision.decision == "deny"
        assert "custom_danger" in decision.reasoning


class TestMainFunction:
    """Test cases for the main CLI function."""

    def test_main_with_valid_input(self, capsys):
        """Test main function with valid input."""
        valid_input = {
            "tool_name": "Write",
            "tool_input": {"file_path": "test.txt", "content": "hello"},
        }

        with patch("sys.stdin", StringIO(json.dumps(valid_input))):
            with patch("sys.exit") as mock_exit:
                main()
                mock_exit.assert_called_with(0)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "hookSpecificOutput" in output

    def test_main_with_invalid_input(self, capsys):
        """Test main function with invalid input."""
        with patch("sys.stdin", StringIO("invalid json")):
            with patch("sys.exit") as mock_exit:
                main()
                mock_exit.assert_called_with(1)  # Non-blocking error

        captured = capsys.readouterr()
        assert "Input error" in captured.err

    def test_main_with_empty_input(self, capsys):
        """Test main function with empty input."""
        with patch("sys.stdin", StringIO("")):
            with patch("sys.exit") as mock_exit:
                main()
                mock_exit.assert_called_with(1)  # Non-blocking error

        captured = capsys.readouterr()
        assert "Input error" in captured.err

    def test_main_with_evaluation_error(self, capsys):
        """Test main function with evaluation error."""
        valid_input = {"tool_name": "Test"}

        with patch("sys.stdin", StringIO(json.dumps(valid_input))):
            with patch(
                "superego_mcp.cli_eval.CLIEvaluator.evaluate_from_stdin"
            ) as mock_eval:
                mock_eval.side_effect = RuntimeError("Evaluation failed")
                with patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_called_with(2)  # Blocking error

        captured = capsys.readouterr()
        assert "Evaluation error" in captured.err

    def test_main_with_unexpected_error(self, capsys):
        """Test main function with unexpected error."""
        with patch("superego_mcp.cli_eval.CLIEvaluator") as mock_evaluator:
            mock_evaluator.side_effect = Exception("Unexpected error")
            with patch("sys.exit") as mock_exit:
                main()
                mock_exit.assert_called_with(2)  # Blocking error

        captured = capsys.readouterr()
        assert "Unexpected error" in captured.err
