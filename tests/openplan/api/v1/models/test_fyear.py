import pytest

from openplan.api.v1.models.fyear import FinancialYearPath


@pytest.mark.parametrize("fyear", ["199091", "199900", "200001", "202122"])
def test_is_valid_fyear_true(fyear):
    assert FinancialYearPath.is_valid_fyear(fyear)


@pytest.mark.parametrize("fyear", ["199092", "1", "189091"])
def test_is_valid_fyear_false(fyear):
    assert not FinancialYearPath.is_valid_fyear(fyear)


def test_FinancialYearPath_valid():
    fyear = "202122"
    fy_path = FinancialYearPath(fyear=fyear)
    assert fy_path.fyear == fyear


def test_FinancialYearPath_invalid():
    with pytest.raises(ValueError):
        FinancialYearPath(fyear="199092")
