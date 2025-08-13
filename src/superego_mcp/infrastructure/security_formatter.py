"""Security decision formatting for interactive visibility."""

import sys
from typing import TextIO

from superego_mcp.domain.models import Decision, ToolRequest


class SecurityDecisionFormatter:
    """Formats security decisions with colored output for interactive mode."""

    # ANSI color codes
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    def __init__(self, output: TextIO = sys.stderr, use_colors: bool = True):
        """Initialize formatter.

        Args:
            output: Output stream (default: stderr to avoid interfering with MCP protocol)
            use_colors: Whether to use ANSI color codes
        """
        self.output = output
        self.use_colors = use_colors and output.isatty()

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if not self.use_colors:
            return text
        return f"{color}{text}{self.RESET}"

    def format_decision(self, request: ToolRequest, decision: Decision) -> str:
        """Format a security decision for display.

        Args:
            request: The tool request that was evaluated
            decision: The security decision

        Returns:
            Formatted decision string
        """
        # Choose color and icon based on action
        if decision.action == "allow":
            icon = "✅"
            color = self.GREEN
            action_text = "ALLOWED"
        elif decision.action == "deny":
            icon = "❌"
            color = self.RED
            action_text = "DENIED"
        elif decision.action == "sample":
            icon = "🤖"
            color = self.YELLOW
            action_text = "REQUIRES EVALUATION"

        # Format the main decision line
        tool_name = self._colorize(request.tool_name, self.CYAN)
        action_colored = self._colorize(action_text, color)

        lines = [
            f"{icon} {self._colorize('SECURITY DECISION', self.BOLD)} {action_colored}",
            f"   Tool: {tool_name}",
            f"   Reason: {decision.reason}",
        ]

        # Add rule information if available
        if decision.rule_id:
            lines.append(f"   Rule: {self._colorize(decision.rule_id, self.MAGENTA)}")

        # Add confidence and timing
        confidence_pct = f"{decision.confidence * 100:.1f}%"
        lines.append(f"   Confidence: {self._colorize(confidence_pct, self.BLUE)}")

        if decision.processing_time_ms > 0:
            lines.append(f"   Processing: {decision.processing_time_ms}ms")

        # Add AI evaluation details for sample actions
        if decision.action == "sample" and decision.ai_evaluation:
            lines.append(f"   {self._colorize('AI Evaluation:', self.YELLOW)}")
            ai_eval = decision.ai_evaluation

            if "decision" in ai_eval:
                ai_decision = ai_eval["decision"].upper()
                lines.append(f"     AI Decision: {ai_decision}")

            if "reasoning" in ai_eval:
                lines.append(f"     AI Reasoning: {ai_eval['reasoning']}")

            if "risk_factors" in ai_eval and ai_eval["risk_factors"]:
                risk_list = ", ".join(ai_eval["risk_factors"])
                lines.append(
                    f"     Risk Factors: {self._colorize(risk_list, self.RED)}"
                )

        # Add risk factors from decision
        if decision.risk_factors:
            risk_list = ", ".join(decision.risk_factors)
            lines.append(f"   Risk Factors: {self._colorize(risk_list, self.RED)}")

        # Add approval requirement notice
        if decision.requires_approval:
            approval_text = self._colorize("⚠️  USER APPROVAL REQUIRED", self.YELLOW)
            lines.append(f"   {approval_text}")

        return "\n".join(lines)

    def display_decision(self, request: ToolRequest, decision: Decision) -> None:
        """Display a formatted security decision.

        Args:
            request: The tool request that was evaluated
            decision: The security decision
        """
        formatted = self.format_decision(request, decision)
        print(formatted, file=self.output)
        print("", file=self.output)  # Add blank line for readability
        self.output.flush()

    def display_separator(self, title: str = "SECURITY EVALUATION") -> None:
        """Display a separator line.

        Args:
            title: Title to display in the separator
        """
        separator = "─" * 60
        title_colored = self._colorize(title, self.BOLD)
        print(f"\n{separator}", file=self.output)
        print(f" {title_colored}", file=self.output)
        print(separator, file=self.output)
        self.output.flush()

    def display_summary(self, decisions: list[tuple[ToolRequest, Decision]]) -> None:
        """Display a summary of security decisions.

        Args:
            decisions: List of (request, decision) tuples
        """
        if not decisions:
            return

        # Count decisions by type
        counts = {"allow": 0, "deny": 0, "sample": 0}
        for _, decision in decisions:
            counts[decision.action] = counts.get(decision.action, 0) + 1

        self.display_separator("SECURITY SUMMARY")

        total = len(decisions)
        print(f"Total Requests: {total}", file=self.output)

        if counts["allow"] > 0:
            allowed_text = self._colorize(f"✅ Allowed: {counts['allow']}", self.GREEN)
            print(f"  {allowed_text}", file=self.output)

        if counts["deny"] > 0:
            denied_text = self._colorize(f"❌ Denied: {counts['deny']}", self.RED)
            print(f"  {denied_text}", file=self.output)

        if counts["sample"] > 0:
            sample_text = self._colorize(
                f"🤖 Evaluated: {counts['sample']}", self.YELLOW
            )
            print(f"  {sample_text}", file=self.output)

        print("", file=self.output)
        self.output.flush()
