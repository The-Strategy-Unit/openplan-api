from io import BytesIO
import json
import os
import unittest
from unittest.mock import Mock, call, patch

from azure.core.exceptions import ResourceNotFoundError
import polars as pl
from polars.testing import assert_frame_equal

from openplan.api.v1 import data
from openplan.api.v1.cache import BlobCache
from openplan.api.v1.settings import StorageSettings


class DatasetReaderTests(unittest.TestCase):
    def setUp(self):
        self.storage = StorageSettings("syntheticstorage", "synthetic-inputs")
        self.enterContext(patch.dict(os.environ, {
            "OPENPLAN_STORAGE_ACCOUNT_NAME": self.storage.account_name,
            "OPENPLAN_STORAGE_CONTAINER_NAME": self.storage.container_name,
            "OPENPLAN_CACHE_TTL_SECONDS": "300",
            "OPENPLAN_CACHE_MAX_BYTES": "134217728",
        }))

    def test_csv_can_be_collected_after_the_download_buffer_closes(self):
        stream = BytesIO(b"sex,age,2024,2030\n1,0,10.5,12.0\n1,1,,24.0\n")
        with patch.object(data, "_read_azure_file", return_value=stream) as read:
            frame = data.read_azure_csv_file("synthetic/demographics.csv")
        self.assertTrue(stream.closed)
        self.assertIsInstance(frame, pl.LazyFrame)
        assert_frame_equal(frame.collect(), pl.DataFrame({
            "sex": [1, 1], "age": [0, 1],
            "2024": [10.5, None], "2030": [12.0, 24.0],
        }))
        read.assert_called_once_with("synthetic/demographics.csv", settings=self.storage)

    def test_parquet_can_be_filtered_after_the_download_buffer_closes(self):
        expected = pl.DataFrame({
            "provider": ["R01", "R02"], "fyear": [202425, 202526],
            "denominator": [100.0, 120.0], "std_rate": [1.2, 1.5],
        })
        payload = BytesIO()
        expected.write_parquet(payload)
        stream = BytesIO(payload.getvalue())
        with patch.object(data, "_read_azure_file", return_value=stream) as read:
            frame = data.read_azure_parquet_file("synthetic/rates.parquet")
        self.assertTrue(stream.closed)
        self.assertIsInstance(frame, pl.LazyFrame)
        assert_frame_equal(
            frame.filter(pl.col("provider") == "R02").collect(), expected.tail(1),
        )
        read.assert_called_once_with("synthetic/rates.parquet", settings=self.storage)

    def test_json_preserves_nested_values_and_unicode(self):
        expected = {"R01": {"v1.0": {"name": "Synthetic café", "peers": [], "note": None}}}
        stream = BytesIO(json.dumps(expected, ensure_ascii=False).encode("utf-8"))
        with patch.object(data, "_read_azure_file", return_value=stream) as read:
            actual = data.read_azure_json_file("synthetic/peers.json")
        self.assertEqual(actual, expected)
        self.assertTrue(stream.closed)
        read.assert_called_once_with("synthetic/peers.json", settings=self.storage)

    def test_malformed_csv_is_rejected_when_collected(self):
        stream = BytesIO(b"sex,age,2024\n1,0,10.5\n1,1,20.0,unexpected\n")
        with patch.object(data, "_read_azure_file", return_value=stream):
            with self.assertRaises(pl.exceptions.PolarsError):
                data.read_azure_csv_file("synthetic/malformed.csv").collect()
        self.assertTrue(stream.closed)

    def test_malformed_parquet_is_rejected(self):
        stream = BytesIO(b"This is not a Parquet file")
        with patch.object(data, "_read_azure_file", return_value=stream):
            with self.assertRaises(pl.exceptions.PolarsError):
                data.read_azure_parquet_file("synthetic/malformed.parquet").collect()
        self.assertTrue(stream.closed)

    def test_malformed_json_is_rejected(self):
        stream = BytesIO(b'{"peers": [}')
        with patch.object(data, "_read_azure_file", return_value=stream):
            with self.assertRaises(json.JSONDecodeError):
                data.read_azure_json_file("synthetic/malformed.json")
        self.assertTrue(stream.closed)

    def test_missing_blobs_preserve_the_storage_error(self):
        for reader, filename in (
            (data.read_azure_csv_file, "synthetic/missing.csv"),
            (data.read_azure_parquet_file, "synthetic/missing.parquet"),
            (data.read_azure_json_file, "synthetic/missing.json"),
        ):
            error = ResourceNotFoundError("Synthetic missing blob")
            with self.subTest(filename=filename), patch.object(
                data, "_read_azure_file", side_effect=error,
            ) as read:
                with self.assertRaises(ResourceNotFoundError) as raised:
                    reader(filename)
                self.assertIs(raised.exception, error)
                read.assert_called_once_with(filename, settings=self.storage)


    def test_json_callers_cannot_mutate_the_cached_payload(self):
        with patch.object(data, "_read_azure_file", return_value=BytesIO(b'{"peers": ["R02"]}')) as read:
            first = data.read_azure_json_file("synthetic/peers.json")
            first["peers"].append("Changed by caller")
            self.assertEqual(data.read_azure_json_file("synthetic/peers.json"), {"peers": ["R02"]})
        read.assert_called_once_with("synthetic/peers.json", settings=self.storage)

    def test_storage_accounts_and_containers_do_not_share_cache_entries(self):
        def download(filename, *, settings):
            return BytesIO(json.dumps({"account": settings.account_name, "container": settings.container_name}).encode())

        with patch.object(data, "_read_azure_file", side_effect=download) as read:
            expected = {"account": self.storage.account_name, "container": self.storage.container_name}
            self.assertEqual(data.read_azure_json_file("synthetic/shared.json"), expected)
            for overrides in (
                {"OPENPLAN_STORAGE_ACCOUNT_NAME": "otherstorage"},
                {"OPENPLAN_STORAGE_CONTAINER_NAME": "other-container"},
            ):
                with patch.dict(os.environ, overrides):
                    selected = data.get_storage_settings()
                    self.assertEqual(data.read_azure_json_file("synthetic/shared.json"), {
                        "account": selected.account_name, "container": selected.container_name,
                    })
            self.assertEqual(data.read_azure_json_file("synthetic/shared.json"), expected)
        self.assertEqual(read.call_count, 3)

    def test_expired_reader_data_is_reloaded(self):
        clock = Mock(return_value=0)
        with patch.object(data, "_blob_cache", BlobCache(clock=clock)), patch.object(
            data, "_read_azure_file", side_effect=[BytesIO(b'{"revision": 1}'), BytesIO(b'{"revision": 2}')],
        ) as read:
            self.assertEqual(data.read_azure_json_file("synthetic/release.json"), {"revision": 1})
            clock.return_value = 300
            self.assertEqual(data.read_azure_json_file("synthetic/release.json"), {"revision": 2})
        self.assertEqual(read.call_count, 2)

    def test_discovery_reads_bypass_warm_cache_and_cache_configuration(self):
        with patch.object(data, "_read_azure_file", side_effect=[
            BytesIO(b'{"revision": 1}'), BytesIO(b'{"revision": 2}'), BytesIO(b'{"revision": 3}'),
        ]) as read:
            self.assertEqual(data.read_azure_json_file("api/versions.json"), {"revision": 1})
            with patch.dict(os.environ, {"OPENPLAN_CACHE_TTL_SECONDS": "invalid"}):
                self.assertEqual(data.read_azure_json_file_uncached("api/versions.json"), {"revision": 2})
            self.assertEqual(data.read_azure_json_file("api/versions.json"), {"revision": 1})
            self.assertEqual(data.read_azure_json_file_uncached("api/versions.json"), {"revision": 3})
        self.assertEqual(read.call_count, 3)

    def test_invalid_cache_configuration_fails_before_downloading(self):
        with patch.dict(os.environ, {"OPENPLAN_CACHE_MAX_BYTES": "invalid"}), patch.object(data, "_read_azure_file") as read:
            with self.assertRaisesRegex(RuntimeError, "OPENPLAN_CACHE_MAX_BYTES"):
                data.read_azure_json_file("synthetic/peers.json")
        read.assert_not_called()

    def test_zero_configuration_bypasses_retention_in_the_readers(self):
        for name in ("OPENPLAN_CACHE_TTL_SECONDS", "OPENPLAN_CACHE_MAX_BYTES"):
            with self.subTest(name=name), patch.dict(os.environ, {name: "0"}), patch.object(
                data, "_read_azure_file", side_effect=[BytesIO(b'{"revision": 1}'), BytesIO(b'{"revision": 2}')],
            ) as read:
                self.assertEqual(data.read_azure_json_file("synthetic/peers.json"), {"revision": 1})
                self.assertEqual(data.read_azure_json_file("synthetic/peers.json"), {"revision": 2})
                self.assertEqual(read.call_count, 2)

    def test_all_file_formats_share_one_byte_budget(self):
        parquet = BytesIO()
        pl.DataFrame({"n": [1]}).write_parquet(parquet)
        payloads = {
            "synthetic/n.json": b'{"n": 1}',
            "synthetic/n.csv": b"n\n1\n",
            "synthetic/n.parquet": parquet.getvalue(),
        }

        def download(filename, *, settings):
            return BytesIO(payloads[filename])

        with patch.dict(os.environ, {"OPENPLAN_CACHE_MAX_BYTES": str(len(parquet.getvalue()))}), patch.object(
            data, "_read_azure_file", side_effect=download,
        ) as read:
            self.assertEqual(data.read_azure_json_file("synthetic/n.json"), {"n": 1})
            self.assertEqual(data.read_azure_csv_file("synthetic/n.csv").collect().to_dicts(), [{"n": 1}])
            self.assertEqual(data.read_azure_parquet_file("synthetic/n.parquet").collect().to_dicts(), [{"n": 1}])
            self.assertEqual(data.read_azure_json_file("synthetic/n.json"), {"n": 1})
        self.assertEqual(read.call_args_list, [
            call(filename, settings=self.storage) for filename in (
                "synthetic/n.json", "synthetic/n.csv", "synthetic/n.parquet", "synthetic/n.json",
            )
        ])


if __name__ == "__main__":
    unittest.main()
