"""Request handlers for Superego MCP Server endpoints."""

import os
from datetime import datetime
from typing import Any

import structlog

from superego_mcp.domain.models import Decision, ToolRequest
from superego_mcp.domain.services import InterceptionService
from superego_mcp.infrastructure.security_formatter import SecurityDecisionFormatter

logger = structlog.get_logger(__name__)


class SecurityEvaluationHandler:
    """Handler for security evaluation requests."""

    def __init__(
        self, interception_service: InterceptionService, show_decisions: bool = True
    ):
        """Initialize the handler.

        Args:
            interception_service: Service for handling security evaluations
            show_decisions: Whether to display security decisions in interactive mode
        """
        self.interception_service = interception_service
        self.show_decisions = show_decisions
        self.formatter = SecurityDecisionFormatter() if show_decisions else None

    async def handle_evaluate_request(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        agent_id: str,
        session_id: str,
        cwd: str | None = None,
    ) -> Decision:
        """Handle a security evaluation request.

        Args:
            tool_name: Name of the tool being called
            parameters: Tool parameters
            agent_id: ID of the requesting agent
            session_id: Session identifier
            cwd: Current working directory

        Returns:
            Security decision for the request
        """
        request = ToolRequest(
            tool_name=tool_name,
            parameters=parameters,
            agent_id=agent_id,
            session_id=session_id,
            cwd=cwd or os.getcwd(),
            timestamp=datetime.utcnow(),
        )

        try:
            decision = await self.interception_service.evaluate_request(request)

            # Display security decision if enabled
            if self.show_decisions and self.formatter:
                self.formatter.display_decision(request, decision)

            # Log the security decision
            log_data = {
                "tool_name": tool_name,
                "agent_id": agent_id,
                "session_id": session_id,
                "action": decision.action,
                "rule_id": decision.rule_id,
                "confidence": decision.confidence,
                "processing_time_ms": decision.processing_time_ms,
            }

            if decision.action == "deny":
                logger.warning(
                    "Tool request denied", **log_data, reason=decision.reason
                )
            elif decision.action == "sample":
                logger.info(
                    "Tool request requires evaluation",
                    **log_data,
                    reason=decision.reason,
                )
            else:
                logger.debug("Tool request allowed", **log_data, reason=decision.reason)

            return decision

        except Exception as e:
            logger.error(
                "Error processing security evaluation",
                tool_name=tool_name,
                agent_id=agent_id,
                error=str(e),
                exc_info=True,
            )

            # Return a safe default response on error
            return Decision(
                action="deny",
                reason=f"Internal error during security evaluation: {str(e)}",
                rule_id=None,
                confidence=1.0,
                processing_time_ms=0,
            )
