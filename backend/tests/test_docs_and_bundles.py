from pathlib import Path

from app import bundle_utils


ROOT = Path(__file__).resolve().parents[2]


def test_docs_exist_and_nonempty():
    spec = ROOT / 'docs' / 'software_spec.md'
    methods = ROOT / 'docs' / 'methods.md'
    assert spec.exists()
    assert spec.stat().st_size > 10
    assert methods.exists()
    assert methods.stat().st_size > 10


def test_bundle_load_default():
    bundles = bundle_utils.list_bundles()
    assert any('default_simulation' in b for b in bundles)
    data = bundle_utils.load_bundle('default_simulation')
    assert 'name' in data and 'params' in data
