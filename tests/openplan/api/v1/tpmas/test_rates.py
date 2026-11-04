import azure.functions as func
import polars as pl
import pytest

from openplan.api.v1.tpmas import rates


@pytest.mark.parametrize(
    "provider, expected",
    [
        (
            "A",
            [
                {"fyear": 202324, "denominator": 1, "std_rate": 0.1},
                {"fyear": 202425, "denominator": 2, "std_rate": 0.2},
            ],
        ),
        (
            "B",
            [
                {"fyear": 202324, "denominator": 3, "std_rate": 0.3},
                {"fyear": 202425, "denominator": 4, "std_rate": 0.4},
            ],
        ),
    ],
)
def test_get_tpma_rates_for_provider(mocker, provider, expected):
    # arrange
    df = pl.DataFrame(
        {
            "provider": ["A", "A", "B", "B"],
            "fyear": [202324, 202425, 202324, 202425],
            "denominator": [1, 2, 3, 4],
            "std_rate": [0.1, 0.2, 0.3, 0.4],
            "other_column": [5, 6, 7, 8],
        }
    ).lazy()

    mock_read_azure_parquet_file = mocker.patch(
        "openplan.api.v1.tpmas.rates.read_azure_parquet_file", return_value=df
    )

    # act
    actual = rates.get_tpma_rates_for_provider("v1", provider, "tpma1")

    # assert
    mock_read_azure_parquet_file.assert_called_once_with(
        "api/v1/provider/rates/tpma1.parquet"
    )

    assert actual == expected


@pytest.mark.parametrize(
    "fyear, expected",
    [
        (
            202324,
            [
                {"provider": "A", "denominator": 1, "std_rate": 0.1},
                {"provider": "B", "denominator": 3, "std_rate": 0.3},
            ],
        ),
        (
            202425,
            [
                {"provider": "A", "denominator": 2, "std_rate": 0.2},
                {"provider": "B", "denominator": 4, "std_rate": 0.4},
            ],
        ),
    ],
)
def test_get_tpma_rates_for_fyear(mocker, fyear, expected):
    # arrange
    df = pl.DataFrame(
        {
            "provider": ["A", "A", "B", "B"],
            "fyear": [202324, 202425, 202324, 202425],
            "denominator": [1, 2, 3, 4],
            "std_rate": [0.1, 0.2, 0.3, 0.4],
            "other_column": [5, 6, 7, 8],
        }
    ).lazy()

    mock_read_azure_parquet_file = mocker.patch(
        "openplan.api.v1.tpmas.rates.read_azure_parquet_file", return_value=df
    )

    # act
    actual = rates.get_tpma_rates_for_fyear("v1", fyear, "tpma1")

    # assert
    mock_read_azure_parquet_file.assert_called_once_with(
        "api/v1/provider/rates/tpma1.parquet"
    )

    assert actual == expected


def test_route_tpma_rates_for_provider(mocker):
    # arrange
    provider, tpma = "R00", "IP-AA-001"
    mock_provider_path_validate = mocker.patch(
        "openplan.api.v1.tpmas.rates.provider_path_validate",
        return_value=(provider, "dev"),
    )
    mock_tpma_path_validate = mocker.patch(
        "openplan.api.v1.tpmas.rates.tpma_path_validate",
        return_value=(tpma, "dev"),
    )
    mock_get_tpma_rates_for_provider = mocker.patch(
        "openplan.api.v1.tpmas.rates.get_tpma_rates_for_provider",
        return_value=["a", "b", "c"],
    )

    req = func.HttpRequest(
        method="GET",
        url=f"/api/v1/tpmas/provider/provider={provider}/{tpma}",
        body=b"",
        params={},
    )

    # act
    resp = rates.route_tpma_rates_for_provider(req)

    # assert
    assert resp.status_code == 200
    assert resp.get_body() == b'["a", "b", "c"]'
    mock_get_tpma_rates_for_provider.assert_called_once_with("dev", provider, tpma)
    mock_provider_path_validate.assert_called_once_with(req)
    mock_tpma_path_validate.assert_called_once_with(req)


def test_route_tpma_rates_for_fyear(mocker):
    # arrange
    fyear, tpma = "202425", "IP-AA-001"
    mock_financial_year_path_validate = mocker.patch(
        "openplan.api.v1.tpmas.rates.financial_year_path_validate",
        return_value="202425",
    )
    mock_tpma_path_validate = mocker.patch(
        "openplan.api.v1.tpmas.rates.tpma_path_validate",
        return_value=(tpma, "dev"),
    )
    mock_get_tpma_rates_for_fyear = mocker.patch(
        "openplan.api.v1.tpmas.rates.get_tpma_rates_for_fyear",
        return_value=["a", "b", "c"],
    )

    req = func.HttpRequest(
        method="GET",
        url=f"/api/v1/tpmas/provider/fyear={fyear}/{tpma}",
        body=b"",
        params={},
    )

    # act
    resp = rates.route_tpma_rates_for_fyear(req)

    # assert
    assert resp.status_code == 200
    assert resp.get_body() == b'["a", "b", "c"]'
    mock_get_tpma_rates_for_fyear.assert_called_once_with("dev", int(fyear), tpma)
    mock_financial_year_path_validate.assert_called_once_with(req)
    mock_tpma_path_validate.assert_called_once_with(req)
