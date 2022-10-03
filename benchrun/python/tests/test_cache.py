from benchrun.cache import CacheManager


class TestCacheManager:
    def test_init(self) -> None:
        cache = CacheManager()
        assert not cache._drop_failed
        assert not cache._purge_failed
