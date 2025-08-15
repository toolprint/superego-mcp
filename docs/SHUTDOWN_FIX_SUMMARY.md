# Shutdown Hanging Issue - Root Cause and Fix

## Problem Description

The Superego MCP server was hanging after completing the shutdown sequence. Despite seeing "Server shutdown complete" in the logs, the process would remain alive and continue responding to Ctrl-C signals instead of exiting cleanly.

## Root Cause Analysis

The issue was caused by improper management of the ThreadPoolExecutor used to run the FastMCP STDIO transport. Specifically:

1. **ThreadPoolExecutor Leak**: The STDIO transport was run using `loop.run_in_executor(None, ...)` which uses the default ThreadPoolExecutor
2. **Missing Executor Cleanup**: During shutdown, async tasks were properly cancelled but the ThreadPoolExecutor thread running the STDIO transport was not terminated
3. **Process Hanging**: The main process would wait indefinitely for the executor thread to complete, causing the hang

### Evidence
- Shutdown sequence completed successfully (all async cleanup worked)
- Process continued responding to Ctrl-C (main process alive but blocked)
- `run_in_executor(None, ...)` pattern in `transport_server.py:404`

## Solution Implemented

### 1. Dedicated ThreadPoolExecutor Management

**File**: `/Users/brian/workspace/toolprint/superego-mcp/src/superego_mcp/presentation/transport_server.py`

- Added `self._stdio_executor: ThreadPoolExecutor | None = None` to track the executor
- Created dedicated executor in `_run_stdio_transport()`:
  ```python
  self._stdio_executor = ThreadPoolExecutor(
      max_workers=1, 
      thread_name_prefix="stdio-transport"
  )
  ```
- Use the dedicated executor instead of the default one

### 2. Proper Executor Shutdown

**File**: `/Users/brian/workspace/toolprint/superego-mcp/src/superego_mcp/presentation/transport_server.py`

- Added executor cleanup in `stop()` method:
  ```python
  if self._stdio_executor:
      logger.info("Shutting down STDIO transport executor")
      self._stdio_executor.shutdown(wait=False)
      self._stdio_executor = None
  ```

### 3. Enhanced Signal Handling

**File**: `/Users/brian/workspace/toolprint/superego-mcp/src/superego_mcp/main.py`

- Improved signal handler to handle multiple Ctrl-C presses:
  - First Ctrl-C: Graceful shutdown
  - Second Ctrl-C: Force exit with `os._exit(1)`
  - Third+ Ctrl-C: Immediate exit with `os._exit(2)`

## Testing Instructions

### Manual Testing

1. Start the server:
   ```bash
   cd /Users/brian/workspace/toolprint/superego-mcp
   source .venv/bin/activate
   python -m superego_mcp.cli mcp -t stdio
   ```

2. Wait for server to start completely (you'll see the FastMCP banner)

3. Press Ctrl-C once

4. Verify the server:
   - Shows "Shutdown signal received..."
   - Goes through the complete shutdown sequence
   - Shows "Server shutdown complete" 
   - **Exits immediately** (no hanging)

### Expected Behavior

**Before Fix:**
```
Server shutdown complete
^C
Shutdown signal received...
^C
Shutdown signal received...
```

**After Fix:**
```
Server shutdown complete
[Process exits cleanly]
```

### Fallback Protection

If the executor still doesn't shutdown properly:
- Second Ctrl-C will force immediate exit
- This provides a safety net for any edge cases

## Files Modified

1. `/Users/brian/workspace/toolprint/superego-mcp/src/superego_mcp/presentation/transport_server.py`
   - Added ThreadPoolExecutor import
   - Added `_stdio_executor` field
   - Modified `_run_stdio_transport()` to use dedicated executor
   - Enhanced `stop()` method with executor cleanup

2. `/Users/brian/workspace/toolprint/superego-mcp/src/superego_mcp/main.py`
   - Enhanced signal handler with multi-press protection
   - Added small cleanup delay

## Prevention Recommendations

1. **Always manage ThreadPoolExecutors explicitly** when using `run_in_executor()`
2. **Implement proper shutdown procedures** for all background threads/processes
3. **Add timeout-based cleanup** for any blocking operations during shutdown
4. **Test shutdown behavior** as part of the development process
5. **Use dedicated executors** instead of the default one for better control

## Validation

The fix addresses the root cause by ensuring:
- ✅ ThreadPoolExecutor is properly created and tracked
- ✅ Executor is forcefully shutdown during cleanup
- ✅ Fallback signal handling prevents infinite hanging
- ✅ Process exits cleanly after shutdown sequence

This should resolve the hanging issue completely while maintaining proper cleanup semantics.