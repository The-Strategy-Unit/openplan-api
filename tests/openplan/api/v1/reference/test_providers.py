from unittest.mock import Mock

import azure.functions as func
import pytest
from packaging.version import Version
from pydantic import TypeAdapter, ValidationError

from openplan.api.v1 import settings
from openplan.api.v1.reference import providers


def mock_version_validate(x):
    m = Mock()
    m.version = x["version"]
    return m


def test__get_providers(mocker):
    # arrange
    v = {"a": "A", "b": "B"}
    mock_read_azure_json_file = mocker.patch(
        "openplan.api.v1.reference.providers.read_azure_json_file", return_value=v
    )

    # act
    actual = providers._get_providers()

    # assert
    assert actual == v
    mock_read_azure_json_file.assert_called_once_with("api/providers.json")


@pytest.mark.parametrize(
    "version, expected",
    [
        (None, ["b", "c"]),
        ("dev", ["b", "c"]),
        ("v1.0.0", ["a", "b"]),
        ("v2.0.0", ["a", "b", "c"]),
        ("v2.3.0", ["b", "c"]),
        (Version("v1.0.0"), ["a", "b"]),
    ],
)
def test_get_providers(mocker, version, expected):
    # arrange
    mocker.patch(
        "openplan.api.v1.reference.providers._get_providers",
        return_value={
            "a": {"name": "A", "valid_from": "v1.0.0", "valid_to": "v2.3.0"},
            "b": {"name": "B", "valid_from": "v1.0.0", "valid_to": None},
            "c": {"name": "C", "valid_from": "v2.0.0", "valid_to": None},
        },
    )

    # act
    actual = providers.get_providers(version)

    # assert
    assert list(actual.keys()) == expected


def test_is_valid_provider(mocker):
    # arrange
    mock_get_providers = mocker.patch(
        "openplan.api.v1.reference.providers.get_providers",
        return_value=["a", "b", "c"],
    )

    # act
    actual = [providers.is_valid_provider(v, "dev") for v in ["a", "b", "c", "d"]]

    # assert
    assert actual == [True, True, True, False]
    assert mock_get_providers.call_count == 4
    mock_get_providers.assert_any_call("dev")


def test_validate_provider(mocker):
    # arrange
    mocker.patch(
        "openplan.api.v1.reference.providers.is_valid_provider",
        side_effect=lambda value, _info: value in ["a", "b", "c"],
    )

    # act & assert
    for value in ["a", "b", "c"]:
        assert providers.validate_provider(value) == value

    with pytest.raises(ValueError):
        providers.validate_provider("d")


def test_ProviderCode(mocker):
    # arrange
    provider_code_adapter = TypeAdapter(providers.ProviderCode)
    mocker.patch(
        "openplan.api.v1.reference.providers.is_valid_provider",
        side_effect=lambda value, _info: value in ["R00", "A0A0A"],
    )
    # act & assert
    assert provider_code_adapter.validate_python("R00") == "R00"
    assert provider_code_adapter.validate_python("A0A0A") == "A0A0A"
    with pytest.raises(ValidationError):
        provider_code_adapter.validate_python("b")
        provider_code_adapter.validate_python("R01")
        provider_code_adapter.validate_python("A0A0AA")


@pytest.mark.parametrize(
    "params, expected", [({}, "dev"), ({"version": "v1.0.0"}, "v1.0.0")]
)
def test_route_providers(mocker, params, expected):
    # arrange
    import inspect

    route = inspect.unwrap(providers.route_providers)

    settings.CURRENT_APP_VERSION = "dev"
    mock_get_providers = mocker.patch(
        "openplan.api.v1.reference.providers.get_providers",
        return_value=["a", "b", "c"],
    )
    mock_version_query = mocker.patch(
        "openplan.api.v1.reference.providers.VersionQuery",
    )
    mock_version_query.model_validate.side_effect = mock_version_validate

    req = func.HttpRequest(
        method="GET", url="/api/v1/reference/providers", body=b"", params=params
    )

    # act
    resp = route(req)

    # assert
    assert resp.status_code == 200
    assert resp.get_body() == b'["a", "b", "c"]'
    mock_get_providers.assert_called_once_with(expected)
    mock_version_query.model_validate.assert_called_once_with({"version": expected})
