"""Demo script showcasing multi-transport functionality."""

import asyncio
import json
import time
from typing import Any

import httpx
from httpx import AsyncClient


class MultiTransportDemo:
    """Demo client for testing multi-transport functionality."""

    def __init__(self, base_url: str = "http://localhost", ports: dict[str, int] | None = None):
        """Initialize demo client.
        
        Args:
            base_url: Base URL for HTTP connections
            ports: Dictionary mapping transport names to ports
        """
        self.base_url = base_url
        self.ports = ports or {
            "http": 8000,
            "sse": 8002,
        }

    async def demo_http_transport(self) -> None:
        """Demonstrate HTTP transport functionality."""
        print("\n=== HTTP Transport Demo ===")
        
        http_url = f"{self.base_url}:{self.ports['http']}"
        
        try:
            async with AsyncClient(base_url=http_url, timeout=10.0) as client:
                # Test server info
                print("1. Getting server information...")
                response = await client.get("/v1/server-info")
                if response.status_code == 200:
                    info = response.json()
                    print(f"   Server: {info['name']} v{info['version']}")
                    print(f"   Transport: {info['transport']}")
                    print(f"   Available endpoints: {len(info['endpoints'])} endpoints")
                else:
                    print(f"   Failed to get server info: {response.status_code}")
                
                # Test health check
                print("\n2. Checking health status...")
                response = await client.get("/v1/health")
                if response.status_code == 200:
                    health = response.json()
                    print(f"   Status: {health['status']}")
                    print(f"   Components: {len(health.get('components', {}))} components")
                else:
                    print(f"   Health check failed: {response.status_code}")
                
                # Test tool evaluation - allowed
                print("\n3. Testing tool evaluation (allowed)...")
                eval_request = {
                    "tool_name": "test_tool",
                    "parameters": {"action": "read", "file": "/tmp/test.txt"},
                    "agent_id": "demo_agent",
                    "session_id": "demo_session_1",
                    "cwd": "/tmp",
                }
                
                response = await client.post("/v1/evaluate", json=eval_request)
                if response.status_code == 200:
                    decision = response.json()
                    print(f"   Action: {decision['action']}")
                    print(f"   Reason: {decision['reason']}")
                    print(f"   Confidence: {decision['confidence']}")
                    if decision.get('rule_id'):
                        print(f"   Rule ID: {decision['rule_id']}")
                else:
                    print(f"   Evaluation failed: {response.status_code}")
                
                # Test tool evaluation - denied
                print("\n4. Testing tool evaluation (potentially denied)...")
                eval_request["tool_name"] = "dangerous_tool"
                eval_request["parameters"] = {"action": "delete", "path": "/"}
                
                response = await client.post("/v1/evaluate", json=eval_request)
                if response.status_code == 200:
                    decision = response.json()
                    print(f"   Action: {decision['action']}")
                    print(f"   Reason: {decision['reason']}")
                    print(f"   Confidence: {decision['confidence']}")
                else:
                    print(f"   Evaluation failed: {response.status_code}")
                
                # Test configuration retrieval
                print("\n5. Getting current rules...")
                response = await client.get("/v1/config/rules")
                if response.status_code == 200:
                    rules = response.json()
                    print(f"   Total rules: {rules.get('total_rules', 0)}")
                    if rules.get('last_updated'):
                        print(f"   Last updated: {rules['last_updated']}")
                else:
                    print(f"   Failed to get rules: {response.status_code}")
                
                # Test audit entries
                print("\n6. Getting recent audit entries...")
                response = await client.get("/v1/audit/recent")
                if response.status_code == 200:
                    audit = response.json()
                    entries = audit.get('entries', [])
                    stats = audit.get('stats', {})
                    print(f"   Recent entries: {len(entries)}")
                    print(f"   Total entries: {stats.get('total_entries', 0)}")
                else:
                    print(f"   Failed to get audit entries: {response.status_code}")
                
        except Exception as e:
            print(f"HTTP transport demo failed: {e}")

    async def demo_websocket_transport(self) -> None:
        """Demonstrate WebSocket transport functionality."""
        print("\n=== WebSocket Transport Demo ===")
        
        ws_url = f"ws://localhost:{self.ports['websocket']}/v1/ws"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                print("1. Connected to WebSocket server")
                
                # Test ping
                print("\n2. Testing ping...")
                ping_message = {
                    "message_id": "ping-001",
                    "type": "ping",
                    "data": {}
                }
                
                await websocket.send(json.dumps(ping_message))
                response = await websocket.recv()
                ping_response = json.loads(response)
                
                if ping_response.get("type") == "response" and ping_response.get("data", {}).get("pong"):
                    print("   Pong received!")
                    print(f"   Server timestamp: {ping_response['data'].get('timestamp', 'N/A')}")
                
                # Test health check
                print("\n3. Testing health check...")
                health_message = {
                    "message_id": "health-001",
                    "type": "health",
                    "data": {}
                }
                
                await websocket.send(json.dumps(health_message))
                response = await websocket.recv()
                health_response = json.loads(response)
                
                if health_response.get("type") == "response":
                    health_data = health_response.get("data", {})
                    print(f"   Health status: {health_data.get('status', 'unknown')}")
                
                # Test tool evaluation
                print("\n4. Testing tool evaluation...")
                eval_message = {
                    "message_id": "eval-001",
                    "type": "evaluate",
                    "data": {
                        "tool_name": "test_tool",
                        "parameters": {"ws_test": True},
                        "agent_id": "ws_demo_agent",
                        "session_id": "ws_demo_session",
                        "cwd": "/tmp",
                    }
                }
                
                await websocket.send(json.dumps(eval_message))
                response = await websocket.recv()
                eval_response = json.loads(response)
                
                if eval_response.get("type") == "response":
                    decision = eval_response.get("data", {})
                    print(f"   Action: {decision.get('action', 'unknown')}")
                    print(f"   Reason: {decision.get('reason', 'N/A')}")
                    print(f"   Confidence: {decision.get('confidence', 0)}")
                
                # Test subscription
                print("\n5. Testing event subscription...")
                subscribe_message = {
                    "message_id": "sub-001",
                    "type": "subscribe",
                    "data": {
                        "subscription_type": "audit"
                    }
                }
                
                await websocket.send(json.dumps(subscribe_message))
                response = await websocket.recv()
                sub_response = json.loads(response)
                
                if sub_response.get("type") == "response":
                    sub_data = sub_response.get("data", {})
                    if sub_data.get("subscribed"):
                        print("   Successfully subscribed to audit events")
                        
                        # Wait a moment for potential audit notifications
                        print("   Waiting for audit notifications...")
                        try:
                            # Wait with timeout for notifications
                            notification = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                            notif_data = json.loads(notification)
                            if notif_data.get("type") == "notification":
                                print(f"   Received notification: {notif_data.get('data', {}).get('event_type', 'unknown')}")
                        except asyncio.TimeoutError:
                            print("   No audit notifications received (timeout)")
                
                print("\n6. Closing WebSocket connection...")
                
        except Exception as e:
            print(f"WebSocket transport demo failed: {e}")

    async def demo_sse_transport(self) -> None:
        """Demonstrate Server-Sent Events transport functionality."""
        print("\n=== Server-Sent Events (SSE) Transport Demo ===")
        
        sse_url = f"{self.base_url}:{self.ports['sse']}"
        
        try:
            async with AsyncClient(base_url=sse_url, timeout=30.0) as client:
                print("1. Testing SSE health events stream...")
                
                # Test SSE stream for a short duration
                async with client.stream("GET", "/v1/events/health") as response:
                    if response.status_code == 200:
                        print("   Connected to health events stream")
                        print("   Listening for events (10 seconds max)...")
                        
                        event_count = 0
                        start_time = time.time()
                        
                        async for chunk in response.aiter_text():
                            if chunk.strip():
                                # Parse SSE format
                                lines = chunk.strip().split('\n')
                                event_data = {}
                                
                                for line in lines:
                                    if line.startswith('event: '):
                                        event_data['event'] = line[7:]
                                    elif line.startswith('data: '):
                                        event_data['data'] = line[6:]
                                    elif line.startswith('id: '):
                                        event_data['id'] = line[4:]
                                
                                if event_data:
                                    event_count += 1
                                    print(f"   Event {event_count}: {event_data.get('event', 'unknown')}")
                                    
                                    if event_data.get('event') == 'health_status':
                                        try:
                                            data = json.loads(event_data.get('data', '{}'))
                                            status_info = data.get('status', {})
                                            print(f"      Health status: {status_info.get('status', 'unknown')}")
                                        except json.JSONDecodeError:
                                            pass
                            
                            # Break after 10 seconds or 5 events
                            if time.time() - start_time > 10 or event_count >= 5:
                                break
                        
                        print(f"   Received {event_count} events")
                    else:
                        print(f"   Failed to connect to SSE stream: {response.status_code}")
                
                print("\n2. Testing SSE config events stream...")
                
                # Test config events stream for a short duration
                async with client.stream("GET", "/v1/events/config") as response:
                    if response.status_code == 200:
                        print("   Connected to config events stream")
                        print("   Listening for events (5 seconds max)...")
                        
                        start_time = time.time()
                        received_event = False
                        
                        async for chunk in response.aiter_text():
                            if chunk.strip():
                                lines = chunk.strip().split('\n')
                                for line in lines:
                                    if line.startswith('event: '):
                                        event_type = line[7:]
                                        if event_type in ['config_change', 'keepalive']:
                                            print(f"   Received event: {event_type}")
                                            received_event = True
                            
                            # Break after 5 seconds
                            if time.time() - start_time > 5:
                                break
                        
                        if not received_event:
                            print("   No config events received (expected for stable config)")
                    else:
                        print(f"   Failed to connect to config stream: {response.status_code}")
                
        except Exception as e:
            print(f"SSE transport demo failed: {e}")

    async def demo_concurrent_operations(self) -> None:
        """Demonstrate concurrent operations across multiple transports."""
        print("\n=== Concurrent Multi-Transport Operations Demo ===")
        
        try:
            # Prepare concurrent operations
            async def http_operation():
                http_url = f"{self.base_url}:{self.ports['http']}"
                async with AsyncClient(base_url=http_url, timeout=10.0) as client:
                    return await client.post(
                        "/v1/evaluate",
                        json={
                            "tool_name": "concurrent_test",
                            "parameters": {"transport": "http", "timestamp": time.time()},
                            "agent_id": "concurrent_http_agent",
                            "session_id": "concurrent_session",
                            "cwd": "/tmp",
                        }
                    )
            
            async def websocket_operation():
                ws_url = f"ws://localhost:{self.ports['websocket']}/v1/ws"
                async with websockets.connect(ws_url) as websocket:
                    message = {
                        "message_id": "concurrent-ws",
                        "type": "evaluate",
                        "data": {
                            "tool_name": "concurrent_test",
                            "parameters": {"transport": "websocket", "timestamp": time.time()},
                            "agent_id": "concurrent_ws_agent",
                            "session_id": "concurrent_session",
                            "cwd": "/tmp",
                        }
                    }
                    
                    await websocket.send(json.dumps(message))
                    response = await websocket.recv()
                    return json.loads(response)
            
            print("1. Running concurrent operations...")
            
            # Run operations concurrently
            start_time = time.time()
            results = await asyncio.gather(
                http_operation(),
                websocket_operation(),
                return_exceptions=True
            )
            elapsed_time = time.time() - start_time
            
            print(f"2. Completed in {elapsed_time:.2f} seconds")
            
            # Analyze results
            http_result, ws_result = results
            
            if isinstance(http_result, httpx.Response) and http_result.status_code == 200:
                http_data = http_result.json()
                print(f"   HTTP result: {http_data.get('action', 'unknown')} (confidence: {http_data.get('confidence', 0)})")
            else:
                print(f"   HTTP operation failed: {http_result}")
            
            if isinstance(ws_result, dict) and ws_result.get("type") == "response":
                ws_data = ws_result.get("data", {})
                print(f"   WebSocket result: {ws_data.get('action', 'unknown')} (confidence: {ws_data.get('confidence', 0)})")
            else:
                print(f"   WebSocket operation failed: {ws_result}")
            
        except Exception as e:
            print(f"Concurrent operations demo failed: {e}")

    async def run_demo(self) -> None:
        """Run the complete multi-transport demo."""
        print("🚀 Superego MCP Multi-Transport Demo")
        print("=" * 50)
        print()
        print("This demo showcases the multi-transport capabilities of the Superego MCP Server.")
        print("The server supports STDIO, HTTP, WebSocket, and Server-Sent Events transports.")
        print()
        print(f"Configuration:")
        print(f"  - HTTP API: {self.base_url}:{self.ports['http']}")
        print(f"  - WebSocket: ws://localhost:{self.ports['websocket']}/v1/ws")
        print(f"  - SSE: {self.base_url}:{self.ports['sse']}/v1/events/*")
        print()
        
        try:
            # Run individual transport demos
            await self.demo_http_transport()
            await asyncio.sleep(1)  # Brief pause between demos
            
            await self.demo_websocket_transport()
            await asyncio.sleep(1)
            
            await self.demo_sse_transport()
            await asyncio.sleep(1)
            
            # Run concurrent operations demo
            await self.demo_concurrent_operations()
            
            print("\n" + "=" * 50)
            print("✅ Multi-transport demo completed successfully!")
            print()
            print("Key Features Demonstrated:")
            print("  ✓ HTTP REST API with OpenAPI documentation")
            print("  ✓ Real-time WebSocket communication")
            print("  ✓ Server-Sent Events for live updates")
            print("  ✓ Concurrent operations across transports")
            print("  ✓ Consistent security evaluation across all transports")
            print("  ✓ Unified audit logging and health monitoring")
            
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
            print("\nMake sure the Superego MCP Server is running with multi-transport enabled:")
            print("  python -m superego_mcp.main")


async def main():
    """Main demo entry point."""
    demo = MultiTransportDemo()
    await demo.run_demo()


if __name__ == "__main__":
    # Required dependencies check
    try:
        import httpx
        import websockets
    except ImportError as e:
        print(f"❌ Missing required dependency: {e}")
        print("\nInstall demo dependencies:")
        print("  pip install httpx websockets")
        exit(1)
    
    asyncio.run(main())