from app.traces import bench_save, bench_history
from app.bench_store import add_entry, aggregate_by_solver


def test_bench_store_roundtrip():
    add_entry({'solver': 'testsolver', 'mean_sec': 0.001, 'per_1000_rays': 1.0, 'npoints': 64, 'ntest': 2, 'ts': 0})
    agg = aggregate_by_solver()
    assert 'testsolver' in agg
    assert agg['testsolver']['mean_per_ray'] > 0
