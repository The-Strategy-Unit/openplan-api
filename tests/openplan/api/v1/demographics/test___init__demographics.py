from unittest.mock import patch

import azure.functions as func
import polars as pl
import pytest

from openplan.api.v1.demographics import (
    DemographicFactorsPath,
    get_demographic_factors,
    route_demographic_factors,
)


@pytest.mark.parametrize(
    "start_year,end_year", [(2023, 2024), (2024, 2025), (2024, 2047)]
)
def test_DemographicFactorsPath_valid(start_year, end_year):

    with patch(
        "openplan.api.v1.reference.providers.is_valid_provider", return_value=True
    ):
        DemographicFactorsPath(
            provider="R00",
            start_year=start_year,
            end_year=end_year,
            variant="some_variant",
        )


def test_DemographicFactorsPath_invalid_provider():
    with (
        patch(
            "openplan.api.v1.reference.providers.is_valid_provider", return_value=False
        ),
        pytest.raises(ValueError),
    ):
        DemographicFactorsPath(
            provider="R00",
            start_year=2024,
            end_year=2047,
            variant="some_variant",
        )


@pytest.mark.parametrize(
    "start_year,end_year",
    [
        (2024, 2023),
        (2025, 2024),
        (2022, 2027),
        (2023, 2023),
        (2023, 2090),
        (2024, 2024),
    ],
)
def test_DemographicFactorsPath_invalid_years(start_year, end_year):
    with (
        patch(
            "openplan.api.v1.reference.providers.is_valid_provider", return_value=True
        ),
        pytest.raises(ValueError),
    ):
        DemographicFactorsPath(
            provider="R00",
            start_year=start_year,
            end_year=end_year,
            variant="some_variant",
        )


def test_get_demographic_factors(mocker):
    # arrange
    df = pl.DataFrame(
        {
            "sex": [1] * 10 + [2] * 10,
            "age": list(range(10)) * 2,
            "2024": range(1, 21),
            "2047": range(21, 41),
        }
    ).lazy()

    mock_read_azure_csv_file = mocker.patch(
        "openplan.api.v1.demographics.read_azure_csv_file", return_value=df
    )
    expected_file_path = "api/dev/provider/demographics/population/fyear=202425/provider=a/variant=b/part-0.csv"

    # act
    actual = get_demographic_factors("dev", "population", 202425, "a", "b", 2024, 2047)

    # assert
    mock_read_azure_csv_file.assert_called_once_with(expected_file_path)
    assert actual == {
        "baseline": {
            1: {i: i + 1 for i in range(10)},
            2: {i: i + 11 for i in range(10)},
        },
        "horizon": {
            1: {i: i + 21 for i in range(10)},
            2: {i: i + 31 for i in range(10)},
        },
    }


def test_route_demographic_factors(mocker):
    # arrange
    req = func.HttpRequest(
        method="GET",
        url="",
        body=b"",
        params={},
        route_params={
            "provider": "RL4",
            "start_year": "2024",
            "end_year": "2047",
            "variant": "migration_category",
        },
    )
    mocker.patch(
        "openplan.api.v1.demographics.get_demographic_factors",
        side_effect=["population", "births"],
    )

    # act

    with patch(
        "openplan.api.v1.reference.providers.is_valid_provider", return_value=True
    ):
        resp = route_demographic_factors(req)

    # assert
    assert resp.status_code == 200
    assert resp.get_body() == b'{"population": "population", "births": "births"}'
