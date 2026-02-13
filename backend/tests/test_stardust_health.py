import os
import subprocess
import time
import requests
import shutil
import pytest


RUN = os.environ.get('MOONSTONE_RUN_STARDUST_INTEGRATION_TESTS') == '1'


pytestmark = pytest.mark.skipif(
    not RUN,
    reason='StarDust dev-server integration test is opt-in (set MOONSTONE_RUN_STARDUST_INTEGRATION_TESTS=1)'
)

# Locate StarDust folder; support both embedded and sibling repo layouts
_candidate1 = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'StarDust', 'frontend'))
_candidate2 = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'StarDust', 'frontend'))
if os.path.exists(_candidate1):
    STAR_ROOT = _candidate1
else:
    STAR_ROOT = _candidate2
# Resolve dev-up/down scripts relative to whichever layout is present
DEV_UP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'StarDust', 'scripts', 'dev-up.sh'))
if not os.path.exists(DEV_UP):
    DEV_UP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'StarDust', 'scripts', 'dev-up.sh'))
DEV_DOWN = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'StarDust', 'scripts', 'dev-down.sh'))
if not os.path.exists(DEV_DOWN):
    DEV_DOWN = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'StarDust', 'scripts', 'dev-down.sh'))


@pytest.mark.skipif(shutil.which('bash') is None, reason='bash not available')
def test_stardust_dev_up_and_health():
    # Start dev-up (idempotent)
    p = subprocess.Popen([DEV_UP], cwd=STAR_ROOT)
    # wait for static server to respond on port 4001
    url = 'http://localhost:4001/'
    ok = False
    for _ in range(15):
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                ok = True
                break
        except Exception:
            time.sleep(1)
    # cleanup
    subprocess.run([DEV_DOWN], cwd=STAR_ROOT)
    assert ok, f"StarDust static server did not respond at {url}"
