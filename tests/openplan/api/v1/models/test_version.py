import pytest

from openplan.api.v1.models.version import VersionQuery


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
