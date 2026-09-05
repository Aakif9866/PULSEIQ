import pytest

from app.storage.local import LocalStorageProvider


@pytest.fixture()
def provider(tmp_path):
    return LocalStorageProvider(str(tmp_path))


def test_save_then_open_roundtrips(provider):
    provider.save("owner/dataset.csv", b"a,b\n1,2\n")
    assert provider.open("owner/dataset.csv").read() == b"a,b\n1,2\n"


def test_exists(provider):
    assert provider.exists("owner/missing.csv") is False
    provider.save("owner/present.csv", b"data")
    assert provider.exists("owner/present.csv") is True


def test_delete_is_a_noop_when_missing(provider):
    provider.delete("owner/never-existed.csv")  # must not raise


def test_delete_removes_the_file(provider):
    provider.save("owner/to-delete.csv", b"data")
    assert provider.exists("owner/to-delete.csv") is True
    provider.delete("owner/to-delete.csv")
    assert provider.exists("owner/to-delete.csv") is False


def test_local_path_yields_a_real_readable_path(provider, tmp_path):
    provider.save("owner/x.csv", b"hello")
    with provider.local_path("owner/x.csv") as path:
        assert path.read_bytes() == b"hello"
        assert path.is_relative_to(tmp_path)


def test_save_does_not_leave_a_temp_file_behind(provider, tmp_path):
    provider.save("owner/clean.csv", b"data")
    assert [p.name for p in (tmp_path / "owner").iterdir()] == ["clean.csv"]


def test_path_traversal_is_rejected(provider):
    with pytest.raises(ValueError, match="escapes storage root"):
        provider.save("../../etc/passwd", b"malicious")


def test_save_overwrites_atomically(provider):
    provider.save("owner/versioned.csv", b"version-1")
    provider.save("owner/versioned.csv", b"version-2-longer-content")
    assert provider.open("owner/versioned.csv").read() == b"version-2-longer-content"
