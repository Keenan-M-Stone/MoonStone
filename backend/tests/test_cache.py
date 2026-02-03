from app.cache import cache_get, cache_set


def test_cache_set_and_get():
    req = {'a': 1, 'b': 2}
    value = {'points': [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], 'id': 'test-id'}
    key = cache_set(req, value)
    got = cache_get(req)
    assert got is not None
    assert got['id'] == 'test-id'
