from io import BytesIO

from openplan.api.v1 import data


def test_read_azure_file(mocker):
    # arrange
    mocker.patch(
        "openplan.api.v1.data.DefaultAzureCredential", return_value="credential"
    )
    blob_service_client_mock = mocker.patch("openplan.api.v1.data.BlobServiceClient")
    container_client_mock = blob_service_client_mock().get_container_client
    blob_client_mock = container_client_mock().get_blob_client
    download_blob_mock = blob_client_mock().download_blob
    download_blob_mock().readall.return_value = "file content"

    bytes_mock = mocker.patch("openplan.api.v1.data.BytesIO", return_value="bytes")

    blob_service_client_mock.reset_mock()

    # act
    actual = data._read_azure_file("file")

    # assert
    blob_service_client_mock.assert_called_once_with(
        account_url="https://nhpsa.blob.core.windows.net", credential="credential"
    )
    container_client_mock.assert_called_once_with("inputs-data")
    blob_client_mock.assert_called_once_with("file")
    download_blob_mock.assert_called_once()

    bytes_mock.assert_called_once_with("file content")
    assert actual == "bytes"


def test_read_azure_file_uses_cached_credential(mocker):
    # arrange
    data.__CREDENTIAL = "credential"  # ty: ignore[invalid-assignment]
    mock_credential = mocker.patch("openplan.api.v1.data.DefaultAzureCredential")
    blob_service_client_mock = mocker.patch("openplan.api.v1.data.BlobServiceClient")
    container_client_mock = blob_service_client_mock().get_container_client
    blob_client_mock = container_client_mock().get_blob_client
    download_blob_mock = blob_client_mock().download_blob
    download_blob_mock().readall.return_value = "file content"

    mocker.patch("openplan.api.v1.data.BytesIO", return_value="bytes")

    blob_service_client_mock.reset_mock()

    # act
    data._read_azure_file("file")

    # assert
    mock_credential.assert_not_called()


def test_read_azure_parquet_file(mocker):
    # arrange
    mock_scan_parquet = mocker.patch(
        "openplan.api.v1.data.pl.scan_parquet", return_value="lazyframe"
    )
    v = BytesIO(b"file content")
    mock_read_azure_file = mocker.patch(
        "openplan.api.v1.data._read_azure_file", return_value=v
    )

    # act (call twice to test caching)
    actual1 = data.read_azure_parquet_file("file")
    actual2 = data.read_azure_parquet_file("file")

    # assert
    mock_read_azure_file.assert_called_once_with("file")
    mock_scan_parquet.assert_called_once_with(v)
    assert actual1 == "lazyframe"
    assert actual2 == "lazyframe"


def test_read_azure_csv_file(mocker):
    # arrange
    mock_scan_csv = mocker.patch(
        "openplan.api.v1.data.pl.scan_csv", return_value="lazyframe"
    )
    v = BytesIO(b"file content")
    mock_read_azure_file = mocker.patch(
        "openplan.api.v1.data._read_azure_file", return_value=v
    )

    # act (call twice to test caching)
    actual1 = data.read_azure_csv_file("file")
    actual2 = data.read_azure_csv_file("file")

    # assert
    mock_read_azure_file.assert_called_once_with("file")
    mock_scan_csv.assert_called_once_with(v)
    assert actual1 == "lazyframe"
    assert actual2 == "lazyframe"


def test_read_azure_json_file(mocker):
    # arrange
    v = BytesIO(b'{"key": "value"}')
    mock_read_azure_file = mocker.patch(
        "openplan.api.v1.data._read_azure_file", return_value=v
    )

    # act (call twice to test caching)
    actual1 = data.read_azure_json_file("file")
    actual2 = data.read_azure_json_file("file")

    # assert
    mock_read_azure_file.assert_called_once_with("file")
    assert actual1 == {"key": "value"}
    assert actual2 == {"key": "value"}
