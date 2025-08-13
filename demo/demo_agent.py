"""Security Demo Agent for Superego MCP."""

from fast_agent_mcp import fast

@fast.agent(
    name="superego-security-demo",
    servers=["superego"],  # Reference to MCP server in config
    instruction="""You are a security-aware demo agent working with Superego MCP.

Your job is to demonstrate how AI tool requests are evaluated for security compliance.

When performing operations, always:
1. Explain what you're about to do
2. Use appropriate tools for the task
3. Show understanding of security implications
4. Respect any security blocks or modifications

Available operations you can demonstrate:
- File operations: read files, write files, delete files
- System operations: run commands, change permissions  
- Network operations: fetch URLs, make requests
- Search operations: find files, search content

Be educational and explain security concepts to users."""
)
async def security_demo_agent(prompt: str) -> str:
    """Handle user prompts and demonstrate security evaluation."""
    return f"Processing security request: {prompt}"

if __name__ == "__main__":
    fast.run()
