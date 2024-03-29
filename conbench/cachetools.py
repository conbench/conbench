import time
from functools import lru_cache, wraps


def lru_cache_with_ttl(maxsize=None, typed=False, ttl=60):
    """Stdlib LRU cache with a notion of expiration time. Inspired by
    https://stackoverflow.com/a/71634221 and others.

    The maxsize=None default arg makes this (by default) behave like
    functools.cache instead of functools.lru_cache (this is a little cleaner to
    use for caching the return value of functions that have no arguments).
    """

    class Result:
        __slots__ = ("value", "deadline")

        def __init__(self, value, deadline):
            self.value = value
            self.deadline = deadline

    def decorator(func):
        @lru_cache(maxsize=maxsize, typed=typed)
        def cached_func(*args, **kwargs):
            value = func(*args, **kwargs)
            deadline = time.monotonic() + ttl
            return Result(value, deadline)

        @wraps(func)
        def wrapper(*args, **kwargs):
            result = cached_func(*args, **kwargs)
            if result.deadline < time.monotonic():
                result.value = func(*args, **kwargs)
                result.deadline = time.monotonic() + ttl
            return result.value

        wrapper.cache_clear = cached_func.cache_clear
        return wrapper

    return decorator
