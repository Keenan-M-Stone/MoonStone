WebSocket Streaming for Progressive Traces

Overview

- A WebSocket endpoint is available at `/moon/trace/ws`.
- Connect, then send a JSON payload to request a trace:

  {
    "source": {"x":..., "y":..., "z":...},
    "directions": [{"x":..., "y":..., "z":...}, ...],
    "metric": {...},
    "params": {...}
  }

- The server will send back messages of the form:
  - `{'type': 'partial', 'dir_index': N, 'points': [[x,y,z], ...], 'meta': {...}}`
  - `{'type': 'done'}` once the request is complete.

Notes

- The current implementation streams per-direction partial results. For GPU-accelerated batched jobs that execute on the worker, streaming will send the full computed batch per-direction as it completes.
- This POC provides low-latency feedback for interactive UX; the next step is to stream intra-trace progressive samples (sub-chunk updates) for very long traces.
