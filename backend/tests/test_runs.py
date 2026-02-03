import time
from app.runs import _RUNS
from app.runs import submit_run


def test_submit_and_poll(monkeypatch):
    class DummyBT:
        def add_task(self, fn, *args, **kwargs):
            # run inline for test
            fn(*args, **kwargs)
    body = {'solver': 'interactive'}
    res = submit_run(body, DummyBT())
    assert 'run_id' in res
    rid = res['run_id']
    # run should have finished quickly
    run = _RUNS[rid]
    assert run['status'] in ('finished', 'running')
    assert isinstance(run['log'], list)
