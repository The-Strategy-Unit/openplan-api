from unittest.mock import Mock

import azure.functions as func
import pytest
from packaging.version import Version
from pydantic import TypeAdapter, ValidationError

from openplan.api.v1 import tpmas


def test__get_TPMAs(mocker):
    # arrange
    mock_read_azure_json_file = mocker.patch(
        "openplan.api.v1.tpmas.read_azure_json_file", return_value="tpmas"
    )

    # act
    actual = tpmas._get_TPMAs()

    # assert
    assert actual == "tpmas"
    mock_read_azure_json_file.assert_called_once_with("api/tpmas.json")


@pytest.mark.parametrize(
    "version, expected",
    [
        (None, ["TPMA1", "TPMA3"]),
        ("dev", ["TPMA1", "TPMA3"]),
        ("v1.0.0", ["TPMA1"]),
        ("v1.1.0", ["TPMA1", "TPMA2"]),
        ("v1.2.0", ["TPMA1", "TPMA2", "TPMA3"]),
        ("v1.3.0", ["TPMA1", "TPMA3"]),
        (Version("v1.0.0"), ["TPMA1"]),
    ],
)
def test_get_tpmas(mocker, version, expected):
    # arrange
    mock_get_TPMAs = mocker.patch(
        "openplan.api.v1.tpmas._get_TPMAs",
        return_value={
            "TPMA1": {"active_from": "v1.0.0"},
            "TPMA2": {"active_from": "v1.1.0", "active_to": "v1.3.0"},
            "TPMA3": {"active_from": "v1.2.0"},
        },
    )

    # act
    actual = tpmas.get_tpmas(version)

    # assert
    assert list(actual.keys()) == expected
    mock_get_TPMAs.assert_called_once()


def test_is_valid_tpma(mocker):
    # arrange
    mock_get_tpmas = mocker.patch(
        "openplan.api.v1.tpmas.get_tpmas",
        return_value={"TPMA1": {}},
    )

    # act & assert
    assert tpmas.is_valid_tpma("TPMA1", "dev")
    mock_get_tpmas.assert_called_once_with("dev")


def test_is_not_valid_tpma(mocker):
    # arrange
    mock_get_tpmas = mocker.patch(
        "openplan.api.v1.tpmas.get_tpmas",
        return_value={"TPMA1": {}},
    )

    # act & assert
    assert not tpmas.is_valid_tpma("TPMA2", "dev")
    mock_get_tpmas.assert_called_once_with("dev")


def test_validate_tpma(mocker):
    # arrange
    mock_is_valid_tpma = mocker.patch(
        "openplan.api.v1.tpmas.is_valid_tpma",
        side_effect=lambda tpma, _info: tpma == "TPMA1",
    )
    info = Mock()
    info.context = "dev"

    # act & assert
    tpmas.validate_tpma("TPMA1", info)
    mock_is_valid_tpma.assert_called_once_with("TPMA1", "dev")

    mock_is_valid_tpma.reset_mock()

    with pytest.raises(ValueError):
        tpmas.validate_tpma("TPMA2", info)
    mock_is_valid_tpma.assert_called_once_with("TPMA2", "dev")


def test_TPMACode(mocker):
    # arrange
    valid_tpmas = [
        "IP-AA-001",
        "IP-EF-002",
        "OP-AA-011",
        "OP-EF-012",
        "AE-AA-101",
        "AE-EF-102",
    ]
    tpma_code_adapter = TypeAdapter(tpmas.TPMACode)
    mocker.patch(
        "openplan.api.v1.tpmas.is_valid_tpma",
        side_effect=lambda value, _info: value in valid_tpmas,
    )
    # act & assert
    for i in valid_tpmas:
        assert tpma_code_adapter.validate_python(i) == i
    for invalid in ("b", "IP-X-001", "IP-AA", "IP-AA-011"):
        with pytest.raises(ValidationError):
            tpma_code_adapter.validate_python(invalid)


def test_validate_tpma_path(mocker):
    # arrange
    mock_version_validate = mocker.patch(
        "openplan.api.v1.tpmas.version_query_validate",
        return_value="dev",
    )
    mock_validate_tpma = mocker.patch(
        "openplan.api.v1.tpmas.is_valid_tpma", return_value=True
    )

    req = Mock()
    req.route_params = {"tpma": "IP-AA-001"}

    # act
    actual = tpmas.tpma_path_validate(req)

    # assert
    assert actual == ("IP-AA-001", "dev")
    mock_version_validate.assert_called_once_with(req)
    mock_validate_tpma.assert_called_once_with("IP-AA-001", "dev")


def test_route_tpmas(mocker):
    # arrange
    mock_get_tpmas = mocker.patch(
        "openplan.api.v1.tpmas.get_tpmas",
        return_value=["a", "b", "c"],
    )
    mock_version_validate = mocker.patch(
        "openplan.api.v1.tpmas.version_query_validate",
        return_value="dev",
    )

    req = func.HttpRequest(method="GET", url="/api/v1/tpmas", body=b"", params={})

    # act
    resp = tpmas.route_tpmas(req)

    # assert
    assert resp.status_code == 200
    assert resp.get_body() == b'["a", "b", "c"]'
    mock_get_tpmas.assert_called_once_with("dev")
    mock_version_validate.assert_called_once_with(req)
