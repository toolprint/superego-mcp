"""Request queue management for AI sampling and other async operations."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


class Priority(Enum):
    """Request priority levels."""
    
    HIGH = 1
    NORMAL = 2
    LOW = 3
    
    def __lt__(self, other):
        """Enable priority comparison."""
        return self.value < other.value


@dataclass(order=True)
class QueuedRequest:
    """Request in the queue with priority and metadata."""
    
    priority: Priority = field(compare=True)
    enqueue_time: float = field(default_factory=time.time, compare=False)
    request_id: str = field(default="", compare=False)
    request: Any = field(default=None, compare=False)
    future: asyncio.Future = field(default_factory=asyncio.Future, compare=False)
    timeout: float = field(default=30.0, compare=False)
    retry_count: int = field(default=0, compare=False)
    
    def is_expired(self) -> bool:
        """Check if request has exceeded timeout."""
        return time.time() - self.enqueue_time > self.timeout
        
    def get_wait_time(self) -> float:
        """Get time spent waiting in queue."""
        return time.time() - self.enqueue_time


class RequestQueue:
    """Async priority queue for managing AI sampling requests."""
    
    def __init__(
        self,
        max_size: int = 1000,
        default_timeout: float = 30.0,
        max_concurrent: int = 10,
        enable_backpressure: bool = True
    ):
        """Initialize request queue.
        
        Args:
            max_size: Maximum queue size
            default_timeout: Default request timeout in seconds
            max_concurrent: Maximum concurrent request processing
            enable_backpressure: Enable backpressure handling
        """
        self.max_size = max_size
        self.default_timeout = default_timeout
        self.max_concurrent = max_concurrent
        self.enable_backpressure = enable_backpressure
        
        # Priority queue implementation
        self.queue: asyncio.PriorityQueue[QueuedRequest] = asyncio.PriorityQueue(maxsize=max_size)
        
        # Concurrent request tracking
        self.active_requests = 0
        self.active_semaphore = asyncio.Semaphore(max_concurrent)
        
        # Metrics
        self.total_enqueued = 0
        self.total_processed = 0
        self.total_dropped = 0
        self.total_timeout = 0
        self.total_errors = 0
        
        # Queue monitoring
        self._monitor_task: Optional[asyncio.Task] = None
        self._processor_tasks: List[asyncio.Task] = []
        self._running = False
        
    async def start(self, processor: Callable[[Any], Any]) -> None:
        """Start queue processing.
        
        Args:
            processor: Function to process requests
        """
        if self._running:
            return
            
        self._running = True
        self.processor = processor
        
        # Start processor workers
        for i in range(min(self.max_concurrent, 5)):  # Limit initial workers
            task = asyncio.create_task(self._process_requests())
            self._processor_tasks.append(task)
            
        # Start queue monitor
        self._monitor_task = asyncio.create_task(self._monitor_queue())
        
        logger.info(
            "Request queue started",
            max_size=self.max_size,
            max_concurrent=self.max_concurrent
        )
        
    async def stop(self) -> None:
        """Stop queue processing."""
        self._running = False
        
        # Cancel monitor task
        if self._monitor_task:
            self._monitor_task.cancel()
            
        # Cancel processor tasks
        for task in self._processor_tasks:
            task.cancel()
            
        # Wait for tasks to complete
        await asyncio.gather(
            *([self._monitor_task] + self._processor_tasks),
            return_exceptions=True
        )
        
        self._processor_tasks.clear()
        logger.info("Request queue stopped")
        
    async def enqueue(
        self,
        request: Any,
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None,
        request_id: Optional[str] = None
    ) -> Any:
        """Add request to queue.
        
        Args:
            request: Request to enqueue
            priority: Request priority
            timeout: Request timeout (uses default if None)
            request_id: Optional request ID for tracking
            
        Returns:
            Request result
            
        Raises:
            asyncio.QueueFull: If queue is full and backpressure enabled
            asyncio.TimeoutError: If request times out
        """
        if not self._running:
            raise RuntimeError("Queue is not running")
            
        # Generate request ID if not provided
        if request_id is None:
            request_id = f"req_{self.total_enqueued}"
            
        # Create queued request
        queued_request = QueuedRequest(
            priority=priority,
            request_id=request_id,
            request=request,
            timeout=timeout or self.default_timeout
        )
        
        try:
            # Try to add to queue
            if self.enable_backpressure:
                # Non-blocking put with backpressure
                self.queue.put_nowait(queued_request)
            else:
                # Blocking put (waits if full)
                await asyncio.wait_for(
                    self.queue.put(queued_request),
                    timeout=5.0
                )
                
            self.total_enqueued += 1
            
            logger.debug(
                "Request enqueued",
                request_id=request_id,
                priority=priority.name,
                queue_size=self.queue.qsize()
            )
            
            # Wait for result
            return await queued_request.future
            
        except asyncio.QueueFull:
            self.total_dropped += 1
            logger.warning(
                "Queue full, request dropped",
                request_id=request_id,
                queue_size=self.queue.qsize()
            )
            raise
            
        except asyncio.TimeoutError:
            self.total_timeout += 1
            logger.warning(
                "Request enqueue timeout",
                request_id=request_id
            )
            raise
            
    async def _process_requests(self) -> None:
        """Process requests from queue."""
        while self._running:
            try:
                # Get request from queue
                queued_request = await self.queue.get()
                
                # Check if expired
                if queued_request.is_expired():
                    self.total_timeout += 1
                    queued_request.future.set_exception(
                        asyncio.TimeoutError("Request expired in queue")
                    )
                    continue
                    
                # Process with semaphore for concurrency control
                async with self.active_semaphore:
                    self.active_requests += 1
                    try:
                        # Record wait time
                        wait_time = queued_request.get_wait_time()
                        
                        logger.debug(
                            "Processing request",
                            request_id=queued_request.request_id,
                            wait_time=wait_time
                        )
                        
                        # Process request with timeout
                        result = await asyncio.wait_for(
                            self.processor(queued_request.request),
                            timeout=queued_request.timeout - wait_time
                        )
                        
                        # Set result
                        if not queued_request.future.done():
                            queued_request.future.set_result(result)
                            
                        self.total_processed += 1
                        
                    except asyncio.TimeoutError:
                        self.total_timeout += 1
                        if not queued_request.future.done():
                            queued_request.future.set_exception(
                                asyncio.TimeoutError("Request processing timeout")
                            )
                            
                    except Exception as e:
                        self.total_errors += 1
                        logger.error(
                            "Request processing error",
                            request_id=queued_request.request_id,
                            error=str(e)
                        )
                        if not queued_request.future.done():
                            queued_request.future.set_exception(e)
                            
                    finally:
                        self.active_requests -= 1
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Queue processor error", error=str(e))
                await asyncio.sleep(1)
                
    async def _monitor_queue(self) -> None:
        """Monitor queue health and metrics."""
        while self._running:
            try:
                # Log queue metrics
                queue_size = self.queue.qsize()
                
                if queue_size > self.max_size * 0.8:
                    logger.warning(
                        "Queue approaching capacity",
                        queue_size=queue_size,
                        max_size=self.max_size,
                        active_requests=self.active_requests
                    )
                    
                # Clean expired requests periodically
                if queue_size > 0:
                    await self._clean_expired_requests()
                    
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Queue monitor error", error=str(e))
                await asyncio.sleep(5)
                
    async def _clean_expired_requests(self) -> None:
        """Remove expired requests from queue."""
        temp_items = []
        cleaned = 0
        
        # Drain queue to check for expired items
        while not self.queue.empty():
            try:
                item = self.queue.get_nowait()
                if item.is_expired():
                    self.total_timeout += 1
                    item.future.set_exception(
                        asyncio.TimeoutError("Request expired in queue")
                    )
                    cleaned += 1
                else:
                    temp_items.append(item)
            except asyncio.QueueEmpty:
                break
                
        # Re-add non-expired items
        for item in temp_items:
            await self.queue.put(item)
            
        if cleaned > 0:
            logger.info(f"Cleaned {cleaned} expired requests from queue")
            
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics.
        
        Returns:
            Queue statistics
        """
        return {
            "queue_size": self.queue.qsize(),
            "max_size": self.max_size,
            "active_requests": self.active_requests,
            "max_concurrent": self.max_concurrent,
            "total_enqueued": self.total_enqueued,
            "total_processed": self.total_processed,
            "total_dropped": self.total_dropped,
            "total_timeout": self.total_timeout,
            "total_errors": self.total_errors,
            "success_rate": self.total_processed / max(self.total_enqueued, 1),
            "drop_rate": self.total_dropped / max(self.total_enqueued, 1),
            "timeout_rate": self.total_timeout / max(self.total_enqueued, 1),
            "error_rate": self.total_errors / max(self.total_enqueued, 1)
        }
        
    async def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for all queued requests to complete.
        
        Args:
            timeout: Maximum wait time
            
        Returns:
            True if all completed, False if timeout
        """
        start_time = time.time()
        
        while self.queue.qsize() > 0 or self.active_requests > 0:
            if timeout and time.time() - start_time > timeout:
                return False
            await asyncio.sleep(0.1)
            
        return True


class RequestBatcher:
    """Batch similar requests for efficient AI processing."""
    
    def __init__(
        self,
        batch_size: int = 10,
        batch_timeout: float = 0.5,
        similarity_threshold: float = 0.8
    ):
        """Initialize request batcher.
        
        Args:
            batch_size: Maximum batch size
            batch_timeout: Maximum wait time for batch
            similarity_threshold: Minimum similarity for batching
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.similarity_threshold = similarity_threshold
        
        self.pending_batches: Dict[str, List[Tuple[Any, asyncio.Future]]] = {}
        self.batch_timers: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        
    async def add_request(
        self,
        request: Any,
        batch_key: str
    ) -> Any:
        """Add request to batch.
        
        Args:
            request: Request to batch
            batch_key: Key for grouping similar requests
            
        Returns:
            Request result
        """
        future = asyncio.Future()
        
        async with self._lock:
            if batch_key not in self.pending_batches:
                self.pending_batches[batch_key] = []
                # Start timer for this batch
                self.batch_timers[batch_key] = asyncio.create_task(
                    self._batch_timer(batch_key)
                )
                
            self.pending_batches[batch_key].append((request, future))
            
            # Process immediately if batch is full
            if len(self.pending_batches[batch_key]) >= self.batch_size:
                await self._process_batch(batch_key)
                
        return await future
        
    async def _batch_timer(self, batch_key: str) -> None:
        """Timer to process batch after timeout."""
        await asyncio.sleep(self.batch_timeout)
        async with self._lock:
            if batch_key in self.pending_batches:
                await self._process_batch(batch_key)
                
    async def _process_batch(self, batch_key: str) -> None:
        """Process a batch of requests."""
        if batch_key not in self.pending_batches:
            return
            
        # Get batch
        batch = self.pending_batches.pop(batch_key)
        
        # Cancel timer
        if batch_key in self.batch_timers:
            self.batch_timers[batch_key].cancel()
            del self.batch_timers[batch_key]
            
        # Process batch (to be implemented by subclass)
        try:
            requests = [req for req, _ in batch]
            results = await self._execute_batch(batch_key, requests)
            
            # Set results
            for (_, future), result in zip(batch, results):
                if not future.done():
                    future.set_result(result)
                    
        except Exception as e:
            # Set exception for all requests in batch
            for _, future in batch:
                if not future.done():
                    future.set_exception(e)
                    
    async def _execute_batch(
        self,
        batch_key: str,
        requests: List[Any]
    ) -> List[Any]:
        """Execute batch of requests (override in subclass).
        
        Args:
            batch_key: Batch identifier
            requests: List of requests
            
        Returns:
            List of results
        """
        # Default implementation - process individually
        return requests
        
    def calculate_similarity(self, req1: Any, req2: Any) -> float:
        """Calculate similarity between two requests.
        
        Args:
            req1: First request
            req2: Second request
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Default implementation - exact match
        return 1.0 if req1 == req2 else 0.0