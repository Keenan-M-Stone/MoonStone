import os
from app import bundle_utils


def test_docs_exist_and_nonempty():
    assert os.path.exists('docs/software_spec.md')
    assert os.path.getsize('docs/software_spec.md') > 10
    assert os.path.exists('docs/methods.md')
    assert os.path.getsize('docs/methods.md') > 10


def test_bundle_load_default():
    bundles = bundle_utils.list_bundles()
    assert any('default_simulation' in b for b in bundles)
    data = bundle_utils.load_bundle('default_simulation')
    assert 'name' in data and 'params' in data
