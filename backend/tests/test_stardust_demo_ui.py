import requests
import pytest
import shutil
import os


RUN = os.environ.get('MOONSTONE_RUN_STARDUST_INTEGRATION_TESTS') == '1'


pytestmark = pytest.mark.skipif(
    not RUN,
    reason='StarDust demo UI integration test is opt-in (set MOONSTONE_RUN_STARDUST_INTEGRATION_TESTS=1)'
)

# Ensure bash/npm available for dev scripts
@pytest.mark.skipif(shutil.which('bash') is None, reason='bash not available')
def test_stardust_demo_contains_cad_canvas():
    # Start dev-up idempotent (script should be running during CI, test assumes it is)
    url = 'http://localhost:4001/'
    r = requests.get(url, timeout=5)
    assert r.status_code == 200
    # index should have the StarDust title
    assert '<title>StarDust</title>' in r.text, 'Index should be the StarDust demo page'
    # index.html is JS-driven; fetch the referenced bundle and assert it contains our demo marker
    import re
    m = re.search(r"<script[^>]+src=\"([^\"]+)\"", r.text)
    assert m, 'No script tag found in demo index'
    script_url = url.rstrip('/') + m.group(1)
    s = requests.get(script_url, timeout=5)
    assert s.status_code == 200
    assert 'CAD Canvas' in s.text, 'StarDust demo bundle should include "CAD Canvas" marker to verify layout'