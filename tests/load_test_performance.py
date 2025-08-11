"""Load testing script for performance validation."""

import asyncio
import json
import random
import time
from collections import defaultdict
from typing import List

import httpx
import websockets


class LoadTester:
    """Load testing for Superego MCP Server."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.ws_url = "ws://localhost:8001"
        self.metrics_url = "http://localhost:9090"
        self.results = defaultdict(list)
        
    async def test_http_endpoint(self, num_requests: int = 1000):
        """Test HTTP transport performance."""
        print(f"\n🔄 Testing HTTP endpoint with {num_requests} requests...")
        
        async with httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100)
        ) as client:
            tasks = []
            start_time = time.time()
            
            for i in range(num_requests):
                # Vary the requests
                tool_name = random.choice(["read", "write", "edit", "rm", "ls"])
                request_data = {
                    "jsonrpc": "2.0",
                    "method": "evaluate_tool_request",
                    "params": {
                        "tool_name": tool_name,
                        "parameters": {
                            "file": f"/tmp/test_{i}.txt",
                            "content": "test" * random.randint(10, 100)
                        },
                        "agent_id": f"agent_{i % 10}",
                        "session_id": f"session_{i % 20}",
                        "cwd": "/tmp"
                    },
                    "id": i
                }
                
                task = self._make_http_request(client, request_data)
                tasks.append(task)
                
                # Rate limiting to avoid overwhelming
                if i % 100 == 0:
                    await asyncio.sleep(0.1)
            
            # Wait for all requests
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Calculate statistics
            total_time = time.time() - start_time
            successful = sum(1 for r in responses if not isinstance(r, Exception))
            errors = sum(1 for r in responses if isinstance(r, Exception))
            
            # Get response times
            response_times = [r for r in self.results["http_response_times"] if r > 0]
            response_times.sort()
            
            print(f"\n📊 HTTP Load Test Results:")
            print(f"Total requests: {num_requests}")
            print(f"Successful: {successful}")
            print(f"Errors: {errors}")
            print(f"Total time: {total_time:.2f}s")
            print(f"Throughput: {num_requests / total_time:.2f} req/s")
            
            if response_times:
                print(f"\nLatency percentiles:")
                print(f"P50: {response_times[int(len(response_times) * 0.50)]:.3f}s")
                print(f"P90: {response_times[int(len(response_times) * 0.90)]:.3f}s")
                print(f"P95: {response_times[int(len(response_times) * 0.95)]:.3f}s")
                print(f"P99: {response_times[int(len(response_times) * 0.99)]:.3f}s")
                
    async def _make_http_request(self, client: httpx.AsyncClient, data: dict):
        """Make a single HTTP request and record timing."""
        start_time = time.time()
        try:
            response = await client.post(
                f"{self.base_url}/mcp/v1/invoke",
                json=data,
                timeout=10.0
            )
            response_time = time.time() - start_time
            self.results["http_response_times"].append(response_time)
            
            if response.status_code != 200:
                self.results["http_errors"].append(response.status_code)
                
            return response.json()
        except Exception as e:
            self.results["http_errors"].append(str(e))
            return e
            
    async def test_websocket_connections(self, num_connections: int = 100):
        """Test WebSocket concurrent connections."""
        print(f"\n🔄 Testing WebSocket with {num_connections} concurrent connections...")
        
        connections = []
        start_time = time.time()
        
        # Create connections
        for i in range(num_connections):
            try:
                ws = await websockets.connect(self.ws_url)
                connections.append(ws)
                
                # Send initial request
                request = {
                    "jsonrpc": "2.0",
                    "method": "evaluate_tool_request",
                    "params": {
                        "tool_name": "ls",
                        "parameters": {"path": "/tmp"},
                        "agent_id": f"ws_agent_{i}",
                        "session_id": f"ws_session_{i}",
                        "cwd": "/tmp"
                    },
                    "id": i
                }
                await ws.send(json.dumps(request))
                
            except Exception as e:
                self.results["websocket_errors"].append(str(e))
                
            # Rate limiting
            if i % 10 == 0:
                await asyncio.sleep(0.05)
                
        connection_time = time.time() - start_time
        successful_connections = len(connections)
        
        print(f"\n📊 WebSocket Connection Test Results:")
        print(f"Target connections: {num_connections}")
        print(f"Successful: {successful_connections}")
        print(f"Failed: {num_connections - successful_connections}")
        print(f"Connection time: {connection_time:.2f}s")
        print(f"Connection rate: {successful_connections / connection_time:.2f} conn/s")
        
        # Test message throughput
        if connections:
            await self._test_websocket_throughput(connections[:10])  # Test with 10 connections
            
        # Close connections
        for ws in connections:
            await ws.close()
            
    async def _test_websocket_throughput(self, connections: List):
        """Test WebSocket message throughput."""
        print(f"\n🔄 Testing WebSocket throughput with {len(connections)} connections...")
        
        messages_per_connection = 100
        tasks = []
        
        for i, ws in enumerate(connections):
            task = self._send_websocket_messages(ws, i, messages_per_connection)
            tasks.append(task)
            
        start_time = time.time()
        await asyncio.gather(*tasks)
        duration = time.time() - start_time
        
        total_messages = len(connections) * messages_per_connection
        throughput = total_messages / duration
        
        print(f"\n📊 WebSocket Throughput Results:")
        print(f"Total messages: {total_messages}")
        print(f"Duration: {duration:.2f}s")
        print(f"Throughput: {throughput:.2f} msg/s")
        
    async def _send_websocket_messages(self, ws, conn_id: int, num_messages: int):
        """Send multiple messages through a WebSocket connection."""
        for i in range(num_messages):
            request = {
                "jsonrpc": "2.0",
                "method": "evaluate_tool_request",
                "params": {
                    "tool_name": random.choice(["read", "write", "ls"]),
                    "parameters": {"file": f"/tmp/ws_test_{conn_id}_{i}.txt"},
                    "agent_id": f"ws_agent_{conn_id}",
                    "session_id": f"ws_session_{conn_id}",
                    "cwd": "/tmp"
                },
                "id": f"{conn_id}_{i}"
            }
            
            start_time = time.time()
            await ws.send(json.dumps(request))
            response = await ws.recv()
            response_time = time.time() - start_time
            
            self.results["websocket_response_times"].append(response_time)
            
    async def check_metrics(self):
        """Check metrics endpoint."""
        print("\n🔄 Checking metrics endpoint...")
        
        async with httpx.AsyncClient() as client:
            try:
                # Get Prometheus metrics
                response = await client.get(f"{self.metrics_url}/metrics")
                if response.status_code == 200:
                    print("✅ Prometheus metrics endpoint is working")
                    
                    # Parse some key metrics
                    metrics_text = response.text
                    for line in metrics_text.split('\n'):
                        if 'superego_requests_total' in line and not line.startswith('#'):
                            print(f"  {line.strip()}")
                        elif 'superego_request_duration_seconds_count' in line:
                            print(f"  {line.strip()}")
                            
                # Get metrics summary
                response = await client.get(f"{self.metrics_url}/api/metrics/summary")
                if response.status_code == 200:
                    summary = response.json()
                    print(f"\n📊 Metrics Summary:")
                    print(f"  Uptime: {summary.get('uptime_seconds', 0):.1f}s")
                    
            except Exception as e:
                print(f"❌ Failed to check metrics: {e}")
                
    async def run_full_test(self):
        """Run comprehensive load test."""
        print("🚀 Starting Superego MCP Server Load Test")
        print("=" * 50)
        
        # Check server health first
        await self._check_health()
        
        # Run tests
        await self.test_http_endpoint(num_requests=1000)
        await asyncio.sleep(2)  # Let server recover
        
        await self.test_websocket_connections(num_connections=100)
        await asyncio.sleep(2)  # Let server recover
        
        # Check metrics
        await self.check_metrics()
        
        # Print summary
        self._print_summary()
        
    async def _check_health(self):
        """Check server health before testing."""
        print("\n🔄 Checking server health...")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    health = response.json()
                    print(f"✅ Server is {health['status']}")
                else:
                    print(f"⚠️  Health check returned status {response.status_code}")
            except Exception as e:
                print(f"❌ Server not responding: {e}")
                print("Make sure the server is running with: superego-mcp")
                raise
                
    def _print_summary(self):
        """Print load test summary."""
        print("\n" + "=" * 50)
        print("📊 LOAD TEST SUMMARY")
        print("=" * 50)
        
        # HTTP stats
        http_times = self.results["http_response_times"]
        if http_times:
            print(f"\nHTTP Performance:")
            print(f"  Requests: {len(http_times)}")
            print(f"  Avg latency: {sum(http_times) / len(http_times):.3f}s")
            print(f"  Min latency: {min(http_times):.3f}s")
            print(f"  Max latency: {max(http_times):.3f}s")
            
        # WebSocket stats
        ws_times = self.results["websocket_response_times"]
        if ws_times:
            print(f"\nWebSocket Performance:")
            print(f"  Messages: {len(ws_times)}")
            print(f"  Avg latency: {sum(ws_times) / len(ws_times):.3f}s")
            print(f"  Min latency: {min(ws_times):.3f}s")
            print(f"  Max latency: {max(ws_times):.3f}s")
            
        # Error summary
        total_errors = (
            len(self.results["http_errors"]) +
            len(self.results["websocket_errors"])
        )
        if total_errors > 0:
            print(f"\n⚠️  Total errors: {total_errors}")
            print(f"  HTTP errors: {len(self.results['http_errors'])}")
            print(f"  WebSocket errors: {len(self.results['websocket_errors'])}")
        else:
            print(f"\n✅ No errors detected!")
            
        # Performance targets check
        print(f"\n🎯 Performance Targets:")
        
        # Check latency targets
        if http_times:
            http_times_sorted = sorted(http_times)
            p99_ms = http_times_sorted[int(len(http_times_sorted) * 0.99)] * 1000
            if p99_ms < 50:
                print(f"  ✅ P99 latency: {p99_ms:.1f}ms < 50ms target")
            else:
                print(f"  ❌ P99 latency: {p99_ms:.1f}ms > 50ms target")
                
        # Check throughput target
        if http_times:
            throughput = len(http_times) / sum(http_times)
            if throughput > 1000:
                print(f"  ✅ Throughput: {throughput:.0f} req/s > 1000 req/s target")
            else:
                print(f"  ⚠️  Throughput: {throughput:.0f} req/s < 1000 req/s target")


async def main():
    """Run load tests."""
    tester = LoadTester()
    
    try:
        await tester.run_full_test()
    except KeyboardInterrupt:
        print("\n\n⚠️  Load test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Load test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())