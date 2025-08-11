"""Demo client for testing Superego MCP Server."""

import asyncio
import json
from typing import Any

import httpx


class SuperegoClient:
    """Demo client for testing the Superego MCP server."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the client.
        
        Args:
            base_url: Base URL of the Superego MCP server
        """
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def intercept_tool_request(self,
                                   tool_name: str,
                                   parameters: dict[str, Any],
                                   agent_id: str = "demo-agent",
                                   session_id: str = "demo-session") -> dict[str, Any]:
        """Send a tool interception request.
        
        Args:
            tool_name: Name of the tool
            parameters: Tool parameters
            agent_id: Agent identifier
            session_id: Session identifier
            
        Returns:
            Server response
        """
        request_data = {
            "tool_name": tool_name,
            "parameters": parameters,
            "agent_id": agent_id,
            "session_id": session_id,
            "metadata": {"demo": True}
        }

        response = await self.client.post(
            f"{self.base_url}/intercept",
            json=request_data
        )
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> dict[str, Any]:
        """Check server health.
        
        Returns:
            Health status
        """
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the client."""
        await self.client.aclose()


async def run_demo():
    """Run the demo client."""
    client = SuperegoClient()

    try:
        print("🤖 Superego MCP Demo Client")
        print("=" * 40)

        # Health check
        print("\n1. Health Check")
        health = await client.health_check()
        print(f"   Status: {health.get('status', 'unknown')}")

        # Test cases
        test_cases = [
            {
                "name": "Safe file read",
                "tool_name": "read_file",
                "parameters": {"path": "/home/user/document.txt"}
            },
            {
                "name": "Dangerous file deletion",
                "tool_name": "rm",
                "parameters": {"path": "/etc/passwd"}
            },
            {
                "name": "Network request",
                "tool_name": "curl",
                "parameters": {"url": "https://api.example.com/data"}
            },
            {
                "name": "Search operation",
                "tool_name": "search",
                "parameters": {"query": "python tutorial", "max_results": 50}
            }
        ]

        print("\n2. Tool Interception Tests")
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n   Test {i}: {test_case['name']}")
            print(f"   Tool: {test_case['tool_name']}")
            print(f"   Parameters: {json.dumps(test_case['parameters'], indent=6)}")

            try:
                result = await client.intercept_tool_request(
                    test_case['tool_name'],
                    test_case['parameters']
                )

                action = result.get('action', 'unknown')
                print(f"   Result: {action.upper()}")

                if action == 'block':
                    print(f"   Reason: {result.get('block_reason', 'No reason provided')}")
                elif action == 'modify':
                    modified = result.get('modified_parameters', {})
                    print(f"   Modified: {json.dumps(modified, indent=6)}")
                elif action == 'require_approval':
                    print("   Status: Approval required")

                matched_rule = result.get('metadata', {}).get('matched_rule')
                if matched_rule:
                    print(f"   Matched Rule: {matched_rule}")

            except Exception as e:
                print(f"   Error: {e}")

        print("\n✅ Demo completed!")

    except Exception as e:
        print(f"❌ Demo failed: {e}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run_demo())
