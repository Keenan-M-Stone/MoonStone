import pytest
from app import log_parser

SAMPLE_LOG = """
2026-02-03 12:00:00 ERROR analytic kernel failed: cuda error during launch
2026-02-03 12:00:01 WARNING Dask scheduler not found: No scheduler
2026-02-03 12:00:02 INFO connection: WebSocketDisconnect client closed connection
"""


def test_parse_logs_matches_known_patterns():
    entries = log_parser.parse_logs(SAMPLE_LOG)
    causes = [e['cause'] for e in entries]
    assert any('Analytic device kernel execution error' in c for c in causes)
    assert any('Dask scheduler unreachable' in c for c in causes)
    assert any('WebSocket disconnect' in c for c in causes)


def test_append_to_troubleshoot(tmp_path):
    doc = tmp_path / 'troubleshoot.md'
    entries = log_parser.parse_logs(SAMPLE_LOG)
    res = log_parser.append_to_troubleshoot(str(doc), entries)
    assert res is True
    text = doc.read_text()
    assert 'Auto-detected issues from logs' in text
    assert 'Analytic device kernel' in text or 'kernel' in text
