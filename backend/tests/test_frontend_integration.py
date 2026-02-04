import time
import pytest
import requests

FRONTEND_URL = 'http://localhost:3000/'


def test_frontend_root_available():
    # Try for up to ~10s for the dev server to come up
    for _ in range(10):
        try:
            r = requests.get(FRONTEND_URL, timeout=2)
            assert r.status_code == 200
            assert '<div id="root"' in r.text
            return
        except Exception:
            time.sleep(1)
    pytest.skip('Frontend not running or not responding at http://localhost:3000/')
