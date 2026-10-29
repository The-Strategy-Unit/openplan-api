from unittest.mock import Mock

import pytest

from openplan.api.v1 import settings
from openplan.api.v1.models.version import VersionQuery, version_query_validate


@pytest.mark.parametrize("version", ["dev", "v1.0", "v1.0.0", "v1.2.3"])
def test_is_valid_version_true(version):
    assert VersionQuery.is_valid_version(version)


@pytest.mark.parametrize("version", ["invalid", "1.0", "v1"])
def test_is_valid_version_false(version):
    assert not VersionQuery.is_valid_version(version)


def test_VersionQuery_valid():
    version = "v1.2.3"
    vq = VersionQuery(version=version)
    assert vq.version == version


def test_VersionQuery_invalid():
    with pytest.raises(ValueError):
        VersionQuery(version="invalid")


@pytest.mark.parametrize(
    "params, expected",
    [({}, settings.CURRENT_APP_VERSION), ({"version": "v1.0.0"}, "v1.0.0")],
)
def test_version_query_validate_no_version_set(params, expected):
    # arrange
    req = Mock()
    req.params = params

    # act
    actual = version_query_validate(req)

    # assert
    assert actual == expected
