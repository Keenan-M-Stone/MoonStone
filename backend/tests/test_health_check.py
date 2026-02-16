import json
import os
import subprocess
from pathlib import Path

import pytest

HEALTH = Path(__file__).resolve().parents[2] / 'scripts' / 'diagnostics' / 'health_check.sh'
OUT = Path(__file__).resolve().parents[2] / 'scripts' / 'diagnostics' / 'health_summary.json'


def test_health_check_runs_and_produces_json():
    if os.environ.get('MOONSTONE_RUN_HEALTH_CHECK') not in ('1', 'true', 'TRUE', 'yes', 'YES'):
        pytest.skip('Health-check script is opt-in (set MOONSTONE_RUN_HEALTH_CHECK=1)')
    # run the health check
    subprocess.run(['bash', str(HEALTH)], capture_output=True, text=True, timeout=180)
    # script may return non-zero if some checks fail; we still expect JSON to be produced
    assert OUT.exists()
    data = json.loads(OUT.read_text())
    assert 'env' in data and 'frontend' in data and 'tests' in data and 'gpu' in data
    # ensure structure of sub-entries
    assert 'exit_code' in data['env']
    assert 'exit_code' in data['tests']
