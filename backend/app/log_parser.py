"""Simple log parser that maps known error patterns to causes and suggested actions.
Provides helpers to append mapped troubleshooting entries to docs/troubleshoot.md.
"""
import re
from typing import List, Dict
from pathlib import Path

PATTERN_MAP = [
    (re.compile(r"cuda|CUDA|no cuda|no GPU|NVIDIA", re.I),
     "CUDA not available or driver issue",
     "Check that NVIDIA drivers and CUDA toolkit are installed; verify `nvidia-smi` and ensure Python helper detects CUDA (stardust.gpu.is_cuda_available())."),
    (re.compile(r"dask.*scheduler|No scheduler|scheduler not found", re.I),
     "Dask scheduler unreachable",
     "Ensure the Dask scheduler is running and network reachable; verify worker resource tags if using GPU resources."),
    (re.compile(r"WebSocketDisconnect|websocket.*disconnect", re.I),
     "WebSocket disconnect",
     "Client network or server-side exception; check server logs and client connectivity; retry streaming or use single-shot endpoint."),
    (re.compile(r"analytic kernel failed|kernel.*exception|cuda.*exception", re.I),
     "Analytic device kernel execution error",
     "Inspect server logs for kernel stacktrace; try `analytic=false` to use approximate kernel; collect kernel logs and GPU status."),
    (re.compile(r"Trace failed|trace.*error|internal server error", re.I),
     "Trace computation error",
     "Examine provided trace params and server logs. Reproduce with minimal params and escalate with payload and backend stacktrace."),
]


def parse_logs(log_text: str) -> List[Dict[str, str]]:
    """Return a list of matched troubleshooting entries for the provided log text."""
    entries = []
    for regex, cause, action in PATTERN_MAP:
        if regex.search(log_text):
            entries.append({'pattern': regex.pattern, 'cause': cause, 'action': action})
    return entries


def append_to_troubleshoot(doc_path: str, entries: List[Dict[str, str]]):
    """Append parsed entries to the troubleshoot doc in a simple bullet format."""
    p = Path(doc_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('a') as fh:
        fh.write('\n\n')
        fh.write('## Auto-detected issues from logs\n')
        for e in entries:
            fh.write(f"- **Issue**: {e['cause']}\n  - **Pattern**: `{e['pattern']}`\n  - **Action**: {e['action']}\n")
    return True
