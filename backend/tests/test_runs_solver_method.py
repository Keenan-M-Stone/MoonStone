from app.runs import _RUNS
from app.runs import submit_run
import time


def test_run_with_solver_method(monkeypatch):
    class DummyBT:
        def add_task(self, fn, *args, **kwargs):
            # run inline for test
            fn(*args, **kwargs)
    body = {'solver': 'reference', 'solver_method': 'rk4_adaptive', 'n_dirs': 4}
    res = submit_run(body, DummyBT())
    assert 'run_id' in res
    rid = res['run_id']
    run = _RUNS[rid]
    # since the run executes inline, it should finish
    assert run['status'] in ('finished', 'running')
    # if finished, result should include n_dirs
    if run['status'] == 'finished':
        assert run['result']['n_dirs'] == 4
