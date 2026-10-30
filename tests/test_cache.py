from concurrent.futures import ThreadPoolExecutor
import os
from threading import Event
import unittest
from unittest.mock import Mock, patch

from azure.core.exceptions import ServiceRequestError

from openplan.api.v1.cache import BlobCache
from openplan.api.v1.settings import CacheSettings, get_cache_settings


class BlobCacheTests(unittest.TestCase):
    def setUp(self):
        self.clock = Mock(return_value=0)
        self.cache = BlobCache(clock=self.clock)
        self.policy = CacheSettings(ttl_seconds=300, max_bytes=6)
        self.key = ("account", "container", "blob")

    def test_hits_do_not_extend_expiry(self):
        load = Mock(side_effect=[b"old", b"new"])
        self.assertEqual(self.cache.get(self.key, load, self.policy), b"old")
        self.clock.return_value = 299
        self.assertEqual(self.cache.get(self.key, load, self.policy), b"old")
        self.clock.return_value = 300
        self.assertEqual(self.cache.get(self.key, load, self.policy), b"new")
        self.assertEqual(load.call_count, 2)

    def test_expiry_starts_when_the_download_completes(self):
        def download():
            self.clock.return_value = 50
            return b"old"

        self.cache.get(self.key, download, self.policy)
        load = Mock(return_value=b"new")
        self.clock.return_value = 349
        self.assertEqual(self.cache.get(self.key, load, self.policy), b"old")
        load.assert_not_called()
        self.clock.return_value = 350
        self.assertEqual(self.cache.get(self.key, load, self.policy), b"new")
        load.assert_called_once_with()

    def test_byte_budget_evicts_the_least_recently_used_blob(self):
        a, b, c = [("account", "container", name) for name in ("a", "b", "c")]
        load_a = Mock(return_value=b"aaa")
        load_b = Mock(return_value=b"bbb")
        self.cache.get(a, load_a, self.policy)
        self.cache.get(b, load_b, self.policy)
        self.cache.get(a, load_a, self.policy)
        self.cache.get(c, lambda: b"ccc", self.policy)
        self.assertEqual(self.cache.get(a, load_a, self.policy), b"aaa")
        load_a.assert_called_once_with()
        self.assertEqual(self.cache.get(b, load_b, self.policy), b"bbb")
        self.assertEqual(load_b.call_count, 2)

    def test_expired_bytes_are_reclaimed_before_live_entries_are_evicted(self):
        a, b, c = [("account", "container", name) for name in ("a", "b", "c")]
        self.cache.get(a, lambda: b"aaa", self.policy)
        self.clock.return_value = 100
        load_b = Mock(return_value=b"bbb")
        self.cache.get(b, load_b, self.policy)
        self.clock.return_value = 300
        self.cache.get(c, lambda: b"ccc", self.policy)
        self.assertEqual(self.cache.get(b, load_b, self.policy), b"bbb")
        load_b.assert_called_once_with()

    def test_oversized_blobs_are_served_without_displacing_cached_data(self):
        small = Mock(return_value=b"small")
        self.cache.get(self.key, small, self.policy)
        large = Mock(return_value=b"oversized")
        other = ("account", "container", "large")
        for _ in range(2):
            self.assertEqual(self.cache.get(other, large, self.policy), b"oversized")
        self.assertEqual(large.call_count, 2)
        self.assertEqual(self.cache.get(self.key, small, self.policy), b"small")
        small.assert_called_once_with()

    def test_entry_limit_also_bounds_empty_blobs(self):
        load = Mock(return_value=b"")
        for number in range(BlobCache.MAX_ENTRIES + 1):
            self.cache.get(("account", "container", str(number)), load, self.policy)
        before = load.call_count
        self.cache.get(("account", "container", "0"), load, self.policy)
        self.assertEqual(load.call_count, before + 1)

    def test_zero_expiry_or_budget_disables_retention(self):
        for policy in (CacheSettings(0, 6), CacheSettings(300, 0)):
            with self.subTest(policy=policy):
                load = Mock(side_effect=[b"old", b"new"])
                self.assertEqual(self.cache.get(self.key, load, policy), b"old")
                self.assertEqual(self.cache.get(self.key, load, policy), b"new")
                self.assertEqual(load.call_count, 2)

    def test_policy_changes_invalidate_existing_entries(self):
        load = Mock(side_effect=[b"old", b"new", b"last"])
        self.cache.get(self.key, load, self.policy)
        self.assertEqual(self.cache.get(self.key, load, CacheSettings(20, 6)), b"new")
        self.assertEqual(self.cache.get(self.key, load, CacheSettings(20, 3)), b"last")
        # The new budget is too small for this payload, so it is not retained.
        load.return_value = b"ok"
        load.side_effect = None
        self.assertEqual(self.cache.get(self.key, load, CacheSettings(20, 3)), b"ok")
        self.assertEqual(load.call_count, 4)

    def test_storage_failures_are_not_cached(self):
        load = Mock(side_effect=[ServiceRequestError("Synthetic offline storage"), b"new"])
        with self.assertRaises(ServiceRequestError):
            self.cache.get(self.key, load, self.policy)
        self.assertEqual(self.cache.get(self.key, load, self.policy), b"new")
        self.assertEqual(self.cache.get(self.key, load, self.policy), b"new")
        self.assertEqual(load.call_count, 2)

    def test_failed_refresh_does_not_silently_return_stale_data(self):
        load = Mock(side_effect=[b"old", ServiceRequestError("Synthetic failure"), b"new"])
        self.cache.get(self.key, load, self.policy)
        self.clock.return_value = 300
        with self.assertRaises(ServiceRequestError):
            self.cache.get(self.key, load, self.policy)
        self.assertEqual(self.cache.get(self.key, load, self.policy), b"new")

    def run_shared_download(self, failure=False):
        started, follower_entered, release = Event(), Event(), Event()
        clock_calls = 0

        def clock():
            nonlocal clock_calls
            clock_calls += 1
            # Called under the cache lock: the owner cannot store its result
            # before the second request has inspected the pending download.
            if clock_calls == 2:
                follower_entered.set()
            return 0

        self.clock.side_effect = clock
        error = ServiceRequestError("Synthetic shared failure")

        def download():
            started.set()
            if not release.wait(5):
                raise TimeoutError("Test did not release the download")
            if failure:
                raise error
            return b"shared"

        load = Mock(side_effect=download)
        with ThreadPoolExecutor(max_workers=2) as pool:
            owner = pool.submit(self.cache.get, self.key, load, self.policy)
            try:
                self.assertTrue(started.wait(5))
                follower = pool.submit(self.cache.get, self.key, load, self.policy)
                self.assertTrue(follower_entered.wait(5))
            finally:
                release.set()
            for result in (owner, follower):
                if failure:
                    with self.assertRaises(ServiceRequestError) as raised:
                        result.result(timeout=5)
                    self.assertIs(raised.exception, error)
                else:
                    self.assertEqual(result.result(timeout=5), b"shared")
        load.assert_called_once_with()

    def test_concurrent_requests_share_one_download(self):
        self.run_shared_download()

    def test_failed_download_releases_all_waiters_and_allows_retry(self):
        self.run_shared_download(failure=True)
        self.assertEqual(self.cache.get(self.key, lambda: b"retry", self.policy), b"retry")

    def test_different_blobs_download_in_parallel(self):
        started = (Event(), Event())
        release = Event()

        def download(number):
            started[number].set()
            if not release.wait(5):
                raise TimeoutError("Test did not release both downloads")
            return b"one" if number == 0 else b"two"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                pool.submit(self.cache.get, ("account", "container", str(number)),
                            lambda number=number: download(number), self.policy)
                for number in range(2)
            ]
            try:
                for event in started:
                    self.assertTrue(event.wait(5))
            finally:
                release.set()
            self.assertEqual([result.result(timeout=5) for result in results], [b"one", b"two"])

    def test_clearing_during_a_download_prevents_stale_repopulation(self):
        started, release = Event(), Event()

        def download():
            started.set()
            if not release.wait(5):
                raise TimeoutError("Test did not release the original download")
            return b"old"

        with ThreadPoolExecutor(max_workers=1) as pool:
            original = pool.submit(self.cache.get, self.key, download, self.policy)
            try:
                self.assertTrue(started.wait(5))
                self.cache.clear()
                self.assertEqual(self.cache.get(self.key, lambda: b"new", self.policy), b"new")
            finally:
                release.set()
            self.assertEqual(original.result(timeout=5), b"old")
        unexpected = Mock(side_effect=AssertionError("Fresh data should still be cached"))
        self.assertEqual(self.cache.get(self.key, unexpected, self.policy), b"new")
        unexpected.assert_not_called()


class CacheConfigurationTests(unittest.TestCase):
    def test_defaults_match_the_approved_policy(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_cache_settings(), CacheSettings(300, 128 * 1024 * 1024))

    def test_environment_overrides_are_read_lazily(self):
        with patch.dict(os.environ, {"OPENPLAN_CACHE_TTL_SECONDS": "20", "OPENPLAN_CACHE_MAX_BYTES": "4096"}):
            self.assertEqual(get_cache_settings(), CacheSettings(20, 4096))
            os.environ["OPENPLAN_CACHE_TTL_SECONDS"] = "0"
            self.assertEqual(get_cache_settings(), CacheSettings(0, 4096))

    def test_invalid_settings_identify_the_setting(self):
        for name in ("OPENPLAN_CACHE_TTL_SECONDS", "OPENPLAN_CACHE_MAX_BYTES"):
            for value in ("-1", "", " ", "one", "1.5", "1_000", "３００"):
                with self.subTest(name=name, value=value), patch.dict(os.environ, {name: value}, clear=True):
                    with self.assertRaisesRegex(RuntimeError, name):
                        get_cache_settings()


if __name__ == "__main__":
    unittest.main()
