import pytest
import subprocess

NOTEBOOK = 'docs/methods_notebook.ipynb'


def test_notebook_parses():
    try:
        import nbformat
    except Exception:
        pytest.skip('nbformat not installed')
    nb = nbformat.read(NOTEBOOK, as_version=4)
    assert len(nb.cells) >= 8


@pytest.mark.skipif(
    subprocess.run(['python', '-c', 'import nbconvert'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0,
    reason='nbconvert not installed'
)
def test_notebook_executes():
    # execute notebook (CI may skip this if nbconvert not installed)
    res = subprocess.run(['jupyter', 'nbconvert', '--to', 'notebook', '--execute', NOTEBOOK, '--ExecutePreprocessor.timeout=120', '--output', NOTEBOOK], capture_output=True)
    assert res.returncode == 0, res.stdout.decode() + res.stderr.decode()
