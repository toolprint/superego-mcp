"""Demo script showcasing performance optimization features."""

import asyncio
import json
import time

import httpx
import websockets


async def demo_metrics_dashboard():
    """Demo the monitoring dashboard."""
    print("\n🎯 Performance Monitoring Demo")
    print("=" * 50)
    
    print("\n1️⃣ Monitoring Dashboard")
    print("   Visit: http://localhost:9090/dashboard")
    print("   - Real-time performance metrics")
    print("   - Request latency charts")
    print("   - System health status")
    
    print("\n2️⃣ Prometheus Metrics")
    print("   Visit: http://localhost:9090/metrics")
    print("   - Standard Prometheus format")
    print("   - Ready for Grafana integration")
    
    input("\nPress Enter to continue with performance tests...")


async def demo_response_caching():
    """Demo response caching optimization."""
    print("\n🎯 Response Caching Demo")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # First request (cache miss)
        request_data = {
            "jsonrpc": "2.0",
            "method": "evaluate_tool_request",
            "params": {
                "tool_name": "read",
                "parameters": {"file": "/tmp/test.txt"},
                "agent_id": "demo_agent",
                "session_id": "demo_session",
                "cwd": "/tmp"
            },
            "id": 1
        }
        
        print("\n1️⃣ First request (cache miss):")
        start_time = time.time()
        response = await client.post(
            "http://localhost:8000/mcp/v1/invoke",
            json=request_data
        )
        first_time = time.time() - start_time
        print(f"   Response time: {first_time * 1000:.2f}ms")
        
        # Second identical request (cache hit)
        print("\n2️⃣ Second identical request (cache hit):")
        start_time = time.time()
        response = await client.post(
            "http://localhost:8000/mcp/v1/invoke",
            json=request_data
        )
        second_time = time.time() - start_time
        print(f"   Response time: {second_time * 1000:.2f}ms")
        print(f"   Speed improvement: {first_time / second_time:.1f}x faster! 🚀")
        
        # Check cache stats
        metrics_response = await client.get("http://localhost:9090/api/metrics/summary")
        if metrics_response.status_code == 200:
            metrics = metrics_response.json()
            print(f"\n📊 Cache Statistics:")
            print(f"   Cache hit rate: {metrics.get('cache_hit_rate', 0) * 100:.1f}%")


async def demo_concurrent_requests():
    """Demo concurrent request handling."""
    print("\n🎯 Concurrent Request Handling Demo")
    print("=" * 50)
    
    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=50)
    ) as client:
        # Send 50 concurrent requests
        num_requests = 50
        print(f"\n1️⃣ Sending {num_requests} concurrent requests...")
        
        tasks = []
        for i in range(num_requests):
            request_data = {
                "jsonrpc": "2.0",
                "method": "evaluate_tool_request",
                "params": {
                    "tool_name": "ls",
                    "parameters": {"path": f"/tmp/dir_{i}"},
                    "agent_id": f"agent_{i}",
                    "session_id": "concurrent_demo",
                    "cwd": "/tmp"
                },
                "id": i
            }
            
            task = client.post(
                "http://localhost:8000/mcp/v1/invoke",
                json=request_data
            )
            tasks.append(task)
        
        start_time = time.time()
        responses = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        successful = sum(1 for r in responses if r.status_code == 200)
        throughput = num_requests / total_time
        
        print(f"\n📊 Results:")
        print(f"   Total requests: {num_requests}")
        print(f"   Successful: {successful}")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Throughput: {throughput:.2f} req/s")
        print(f"   Avg latency: {total_time / num_requests * 1000:.2f}ms")


async def demo_ai_request_queue():
    """Demo AI sampling request queue."""
    print("\n🎯 AI Request Queue Demo")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # Send multiple AI sampling requests
        print("\n1️⃣ Sending AI sampling requests (with queue management)...")
        
        tasks = []
        for i in range(5):
            request_data = {
                "jsonrpc": "2.0",
                "method": "evaluate_tool_request",
                "params": {
                    "tool_name": "write",  # This triggers AI sampling
                    "parameters": {
                        "file": f"/sensitive/data_{i}.txt",
                        "content": "potentially sensitive content"
                    },
                    "agent_id": "ai_demo_agent",
                    "session_id": "ai_demo_session",
                    "cwd": "/sensitive"
                },
                "id": i
            }
            
            task = client.post(
                "http://localhost:8000/mcp/v1/invoke",
                json=request_data,
                timeout=30.0
            )
            tasks.append(task)
        
        print("   Requests are queued for AI evaluation...")
        print("   Queue prevents overwhelming AI services")
        
        start_time = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        successful = sum(1 for r in responses 
                        if not isinstance(r, Exception) and r.status_code == 200)
        
        print(f"\n📊 AI Queue Results:")
        print(f"   Total requests: {len(tasks)}")
        print(f"   Successful: {successful}")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Queue prevented AI service overload ✅")


async def demo_websocket_performance():
    """Demo WebSocket performance features."""
    print("\n🎯 WebSocket Performance Demo")
    print("=" * 50)
    
    print("\n1️⃣ Creating persistent WebSocket connections...")
    
    connections = []
    for i in range(5):
        ws = await websockets.connect("ws://localhost:8001")
        connections.append(ws)
    
    print(f"   Created {len(connections)} persistent connections")
    
    print("\n2️⃣ Sending rapid messages through WebSockets...")
    
    start_time = time.time()
    message_count = 0
    
    for i in range(10):
        for j, ws in enumerate(connections):
            request = {
                "jsonrpc": "2.0",
                "method": "evaluate_tool_request",
                "params": {
                    "tool_name": "grep",
                    "parameters": {"pattern": "test", "file": f"/tmp/ws_{j}.log"},
                    "agent_id": f"ws_agent_{j}",
                    "session_id": "ws_demo",
                    "cwd": "/tmp"
                },
                "id": f"{j}_{i}"
            }
            
            await ws.send(json.dumps(request))
            response = await ws.recv()
            message_count += 1
    
    total_time = time.time() - start_time
    
    print(f"\n📊 WebSocket Results:")
    print(f"   Messages sent/received: {message_count}")
    print(f"   Total time: {total_time:.2f}s")
    print(f"   Message rate: {message_count / total_time:.2f} msg/s")
    print(f"   Connection reuse saved overhead ✅")
    
    # Close connections
    for ws in connections:
        await ws.close()


async def demo_real_time_metrics():
    """Demo real-time metrics streaming."""
    print("\n🎯 Real-Time Metrics Streaming Demo")
    print("=" * 50)
    
    print("\n1️⃣ Connecting to SSE metrics stream...")
    
    async with httpx.AsyncClient() as client:
        print("   Streaming metrics via Server-Sent Events")
        print("   (Press Ctrl+C to stop)\n")
        
        try:
            async with client.stream(
                "GET",
                "http://localhost:9090/api/metrics/stream",
                timeout=None
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        print(f"📊 Metrics Update:")
                        print(f"   Uptime: {data.get('uptime_seconds', 0):.1f}s")
                        print(f"   Timestamp: {data.get('timestamp', 'N/A')}")
                        print()
                        
                        # Demo for 5 updates
                        if data.get('uptime_seconds', 0) > 5:
                            break
                            
        except KeyboardInterrupt:
            print("\n   Stream stopped by user")


async def main():
    """Run all performance demos."""
    print("🚀 Superego MCP Server - Performance Optimization Demo")
    print("=" * 70)
    print("\nThis demo showcases the Phase 2 performance optimizations:")
    print("- Response caching for repeated requests")
    print("- Concurrent request handling")
    print("- AI request queue management")
    print("- WebSocket connection pooling")
    print("- Real-time metrics streaming")
    print("- Monitoring dashboard")
    
    print("\n⚠️  Make sure the server is running with optimizations enabled:")
    print("   python -m superego_mcp.main_optimized")
    
    input("\nPress Enter to start the demo...")
    
    try:
        # Check server health
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code != 200:
                print("❌ Server not responding. Please start the server first.")
                return
        
        # Run demos
        await demo_metrics_dashboard()
        await demo_response_caching()
        await demo_concurrent_requests()
        await demo_ai_request_queue()
        await demo_websocket_performance()
        await demo_real_time_metrics()
        
        print("\n✅ Performance demo completed!")
        print("\n📊 Check the monitoring dashboard for detailed metrics:")
        print("   http://localhost:9090/dashboard")
        
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        print("Make sure the optimized server is running.")


if __name__ == "__main__":
    asyncio.run(main())