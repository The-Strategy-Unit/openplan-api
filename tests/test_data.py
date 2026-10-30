from io import BytesIO
import json
import unittest
from unittest.mock import patch

from azure.core.exceptions import ResourceNotFoundError
import polars as pl
from polars.testing import assert_frame_equal

from openplan.api.v1 import data


class DatasetReaderTests(unittest.TestCase):
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
        read.assert_called_once_with("synthetic/demographics.csv")

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
        read.assert_called_once_with("synthetic/rates.parquet")

    def test_json_preserves_nested_values_and_unicode(self):
        expected = {"R01": {"v1.0": {"name": "Synthetic café", "peers": [], "note": None}}}
        stream = BytesIO(json.dumps(expected, ensure_ascii=False).encode("utf-8"))
        with patch.object(data, "_read_azure_file", return_value=stream) as read:
            actual = data.read_azure_json_file("synthetic/peers.json")
        self.assertEqual(actual, expected)
        self.assertTrue(stream.closed)
        read.assert_called_once_with("synthetic/peers.json")

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
                read.assert_called_once_with(filename)


if __name__ == "__main__":
    unittest.main()
