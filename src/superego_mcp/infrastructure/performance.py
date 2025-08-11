"""Performance optimization utilities for Superego MCP Server."""

import asyncio
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with TTL support."""
    
    value: Any
    expires_at: float
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() > self.expires_at


class ResponseCache:
    """LRU cache with TTL for response caching."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """Initialize response cache.
        
        Args:
            max_size: Maximum cache size
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        async with self._lock:
            entry = self.cache.get(key)
            if entry is None:
                return None
                
            if entry.is_expired():
                del self.cache[key]
                return None
                
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            entry.hit_count += 1
            return entry.value
            
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if None)
        """
        async with self._lock:
            ttl = ttl or self.default_ttl
            expires_at = time.time() + ttl
            
            # Remove oldest if at capacity
            if len(self.cache) >= self.max_size and key not in self.cache:
                self.cache.popitem(last=False)
                
            self.cache[key] = CacheEntry(
                value=value,
                expires_at=expires_at
            )
            self.cache.move_to_end(key)
            
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self.cache.clear()
            
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Cache statistics
        """
        async with self._lock:
            total_hits = sum(entry.hit_count for entry in self.cache.values())
            active_entries = sum(
                1 for entry in self.cache.values()
                if not entry.is_expired()
            )
            
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "active_entries": active_entries,
                "total_hits": total_hits,
                "hit_rate": total_hits / max(len(self.cache), 1)
            }


class ConnectionPool:
    """HTTP connection pooling for AI services."""
    
    def __init__(
        self,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        keepalive_expiry: int = 30
    ):
        """Initialize connection pool.
        
        Args:
            max_connections: Maximum total connections
            max_keepalive_connections: Maximum keepalive connections
            keepalive_expiry: Keepalive timeout in seconds
        """
        self.limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            keepalive_expiry=keepalive_expiry
        )
        
        self.client = httpx.AsyncClient(
            limits=self.limits,
            timeout=httpx.Timeout(30.0),
            http2=True
        )
        
    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """Make HTTP request using connection pool.
        
        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments
            
        Returns:
            HTTP response
        """
        return await self.client.request(method, url, **kwargs)
        
    async def close(self) -> None:
        """Close connection pool."""
        await self.client.aclose()
        
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics.
        
        Returns:
            Pool statistics
        """
        return {
            "max_connections": self.limits.max_connections,
            "max_keepalive": self.limits.max_keepalive_connections,
            "keepalive_expiry": self.limits.keepalive_expiry
        }


class ObjectPool:
    """Generic object pool for reducing allocations."""
    
    def __init__(self, factory: callable, max_size: int = 100):
        """Initialize object pool.
        
        Args:
            factory: Factory function to create new objects
            max_size: Maximum pool size
        """
        self.factory = factory
        self.max_size = max_size
        self.pool: List[Any] = []
        self._lock = asyncio.Lock()
        self.created_count = 0
        self.reused_count = 0
        
    async def acquire(self) -> Any:
        """Acquire object from pool.
        
        Returns:
            Object instance
        """
        async with self._lock:
            if self.pool:
                self.reused_count += 1
                return self.pool.pop()
            else:
                self.created_count += 1
                return self.factory()
                
    async def release(self, obj: Any) -> None:
        """Release object back to pool.
        
        Args:
            obj: Object to release
        """
        async with self._lock:
            if len(self.pool) < self.max_size:
                # Reset object state if it has a reset method
                if hasattr(obj, 'reset'):
                    obj.reset()
                self.pool.append(obj)
                
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics.
        
        Returns:
            Pool statistics
        """
        return {
            "pool_size": len(self.pool),
            "max_size": self.max_size,
            "created_count": self.created_count,
            "reused_count": self.reused_count,
            "reuse_rate": self.reused_count / max(self.created_count, 1)
        }


class RequestBatcher:
    """Batch similar requests for efficient processing."""
    
    def __init__(
        self,
        batch_size: int = 10,
        batch_timeout: float = 0.1
    ):
        """Initialize request batcher.
        
        Args:
            batch_size: Maximum batch size
            batch_timeout: Maximum wait time in seconds
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.pending: List[Tuple[Any, asyncio.Future]] = []
        self._lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
        
    async def add_request(self, request: Any) -> Any:
        """Add request to batch.
        
        Args:
            request: Request to batch
            
        Returns:
            Request result
        """
        future = asyncio.Future()
        
        async with self._lock:
            self.pending.append((request, future))
            
            # Start batch processing if not running
            if self._batch_task is None or self._batch_task.done():
                self._batch_task = asyncio.create_task(self._process_batch())
                
        return await future
        
    async def _process_batch(self) -> None:
        """Process pending batch."""
        await asyncio.sleep(self.batch_timeout)
        
        async with self._lock:
            if not self.pending:
                return
                
            # Get batch (up to batch_size)
            batch = self.pending[:self.batch_size]
            self.pending = self.pending[self.batch_size:]
            
        # Process batch (override in subclass)
        results = await self._execute_batch([req for req, _ in batch])
        
        # Set results
        for (_, future), result in zip(batch, results):
            if not future.done():
                future.set_result(result)
                
    async def _execute_batch(self, requests: List[Any]) -> List[Any]:
        """Execute batch of requests (override in subclass).
        
        Args:
            requests: Batch of requests
            
        Returns:
            List of results
        """
        # Default implementation processes individually
        results = []
        for request in requests:
            # Simulate processing
            results.append(request)
        return results


class PerformanceMonitor:
    """Monitor and track performance metrics."""
    
    def __init__(self):
        """Initialize performance monitor."""
        self.timings: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
        
    async def record_timing(self, operation: str, duration: float) -> None:
        """Record operation timing.
        
        Args:
            operation: Operation name
            duration: Duration in seconds
        """
        async with self._lock:
            if operation not in self.timings:
                self.timings[operation] = []
                
            self.timings[operation].append(duration)
            
            # Keep only last 1000 timings
            if len(self.timings[operation]) > 1000:
                self.timings[operation] = self.timings[operation][-1000:]
                
    async def get_percentiles(
        self,
        operation: str,
        percentiles: List[int] = [50, 90, 95, 99]
    ) -> Dict[int, float]:
        """Get timing percentiles for operation.
        
        Args:
            operation: Operation name
            percentiles: Percentiles to calculate
            
        Returns:
            Percentile values
        """
        async with self._lock:
            timings = self.timings.get(operation, [])
            if not timings:
                return {p: 0.0 for p in percentiles}
                
            sorted_timings = sorted(timings)
            result = {}
            
            for p in percentiles:
                idx = int(len(sorted_timings) * p / 100)
                idx = min(idx, len(sorted_timings) - 1)
                result[p] = sorted_timings[idx]
                
            return result
            
    async def get_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get performance statistics.
        
        Args:
            operation: Specific operation or None for all
            
        Returns:
            Performance statistics
        """
        async with self._lock:
            if operation:
                timings = self.timings.get(operation, [])
                if not timings:
                    return {"error": f"No timings for operation: {operation}"}
                    
                return {
                    "operation": operation,
                    "count": len(timings),
                    "mean": sum(timings) / len(timings),
                    "min": min(timings),
                    "max": max(timings),
                    "percentiles": await self.get_percentiles(operation)
                }
            else:
                # Return stats for all operations
                stats = {}
                for op, timings in self.timings.items():
                    if timings:
                        stats[op] = {
                            "count": len(timings),
                            "mean": sum(timings) / len(timings),
                            "min": min(timings),
                            "max": max(timings)
                        }
                return stats


class MemoryOptimizer:
    """Memory optimization utilities."""
    
    @staticmethod
    def intern_strings(data: Any) -> Any:
        """Intern strings to reduce memory usage.
        
        Args:
            data: Data structure to optimize
            
        Returns:
            Optimized data
        """
        if isinstance(data, str):
            return sys.intern(data)
        elif isinstance(data, dict):
            return {
                MemoryOptimizer.intern_strings(k): MemoryOptimizer.intern_strings(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [MemoryOptimizer.intern_strings(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(MemoryOptimizer.intern_strings(item) for item in data)
        else:
            return data
            
    @staticmethod
    def compress_data(data: bytes) -> bytes:
        """Compress data using zlib.
        
        Args:
            data: Data to compress
            
        Returns:
            Compressed data
        """
        import zlib
        return zlib.compress(data, level=6)
        
    @staticmethod
    def decompress_data(data: bytes) -> bytes:
        """Decompress zlib-compressed data.
        
        Args:
            data: Compressed data
            
        Returns:
            Decompressed data
        """
        import zlib
        return zlib.decompress(data)