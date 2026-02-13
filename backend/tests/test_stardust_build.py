import os
import subprocess
import shutil
import pytest


RUN = os.environ.get('MOONSTONE_RUN_STARDUST_INTEGRATION_TESTS') == '1'


pytestmark = pytest.mark.skipif(
    not RUN,
    reason='StarDust build integration test is opt-in (set MOONSTONE_RUN_STARDUST_INTEGRATION_TESTS=1)'
)

# Try common locations for StarDust frontend to support different repo layouts
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
    # fallback: try to find a folder named StarDust in parent of _root_guess
    parent = os.path.abspath(os.path.join(_root_guess, '..'))
    alt = os.path.join(parent, 'StarDust', 'frontend')
    if os.path.isdir(alt):
        STAR_DIR = os.path.abspath(alt)
    else:
        STAR_DIR = os.path.join(_root_guess, 'StarDust', 'frontend')



@pytest.mark.skipif(shutil.which('node') is None, reason='node not available')
def test_stardust_build_creates_dist():
    assert os.path.isdir(STAR_DIR), f"StarDust frontend dir not found at {STAR_DIR}"
    # prefer npm ci when lockfile exists
    cmd_install = ['npm', 'ci'] if os.path.exists(os.path.join(STAR_DIR, 'package-lock.json')) else ['npm', 'install']

    res = subprocess.run(cmd_install, cwd=STAR_DIR, capture_output=True, text=True)
    assert res.returncode == 0, f"npm install failed: {res.stderr}"

    res = subprocess.run(['npm', 'run', 'build', '--silent'], cwd=STAR_DIR, capture_output=True, text=True)
    assert res.returncode == 0, f"StarDust build failed: {res.stderr}\n{res.stdout}"

    dist_index = os.path.join(STAR_DIR, 'dist', 'index.html')
    assert os.path.exists(dist_index), f"dist/index.html not found after build at {dist_index}"
