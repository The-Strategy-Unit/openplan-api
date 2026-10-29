import azure.functions as func
import pytest
from packaging.version import Version

from openplan.api.v1.reference import peers


@pytest.fixture
def mock_peers():
    return {"a": {"v1.0.0": ["b", "c", "d"], "v2.0.0": ["e", "f", "g"]}}


@pytest.mark.parametrize(
    "version, expected",
    (
        (None, ["e", "f", "g"]),
        ("v1.0.0", ["b", "c", "d"]),
        ("v1.9.0", ["b", "c", "d"]),
        ("v2.0.0", ["e", "f", "g"]),
        (Version("v2.0.0"), ["e", "f", "g"]),
    ),
)
def test__get_peers(mocker, version, expected, mock_peers):
    # arrange
    mock_read_azure_json_file = mocker.patch(
        "openplan.api.v1.reference.peers.read_azure_json_file",
        return_value=mock_peers,
    )

    # act
    result = peers._get_peers("a", version)

    # assert
    assert result == expected
    mock_read_azure_json_file.assert_called_once_with("api/peers.json")


def test_route_peers(mocker):
    # arrange
    mock_get_peers = mocker.patch(
        "openplan.api.v1.reference.peers._get_peers",
        return_value=["b", "c", "d"],
    )
    mock_provider_validate = mocker.patch(
        "openplan.api.v1.reference.peers.provider_path_validate",
        return_value=("a", "dev"),
    )

    req = func.HttpRequest(
        method="GET",
        url="/api/v1/reference/peers/a",
        body=b"",
        params={"version": "dev"},
    )

    # act
    resp = peers.route_peers(req)

    # assert
    assert resp.status_code == 200
    assert resp.get_body() == b'["b", "c", "d"]'
    mock_get_peers.assert_called_once_with("a", "dev")
    mock_provider_validate.assert_called_once_with(req)
