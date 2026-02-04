import os
import subprocess
import json
import shutil
import pytest

# Locate StarDust frontend similar to other tests
_root_guess = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_candidates = [
    os.path.join(_root_guess, 'StarDust', 'frontend'),
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'StarDust', 'frontend'),
    os.path.join(os.path.expanduser('~'), 'dev', 'StarDust', 'frontend'),
    os.path.join(os.path.expanduser('~'), 'StarDust', 'frontend'),
]
STAR_DIR = None
for c in _candidates:
    if os.path.isdir(c):
        STAR_DIR = os.path.abspath(c)
        break
if STAR_DIR is None:
    STAR_DIR = os.path.join(_root_guess, 'StarDust', 'frontend')


@pytest.mark.skipif(shutil.which('npm') is None, reason='npm not available')
def test_stardust_audit_has_no_high_or_critical():
    assert os.path.isdir(STAR_DIR), f"StarDust frontend dir not found at {STAR_DIR}"
    # run audit
    res = subprocess.run(['npm', 'audit', '--json'], cwd=STAR_DIR, capture_output=True, text=True)
    assert res.returncode == 0 or res.returncode == 1  # npm audit returns non-zero when vulnerabilities found
    try:
        data = json.loads(res.stdout)
    except Exception:
        pytest.skip('npm audit did not produce json output')
    vul = data.get('metadata', {}).get('vulnerabilities', {})
    high = vul.get('high', 0)
    critical = vul.get('critical', 0)
    assert high == 0 and critical == 0, f"Found high/critical vulnerabilities: high={high}, critical={critical}"
