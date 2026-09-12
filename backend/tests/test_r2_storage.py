"""Unit tests for R2StorageProvider's own logic, with boto3 mocked out —
there are no real Cloudflare R2 credentials available in this environment
(see docs/V2_IMPLEMENTATION_PLAN.md's Phase 7: the provider code already
existed from V1, unverified against a real bucket; this only tests that
the provider calls boto3 correctly, which is the part actually testable
without a real account). Real-bucket verification remains a documented,
honest gap — not claimed here.
"""
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.storage.r2 import R2StorageProvider


@pytest.fixture()
def mock_client():
    with patch("app.storage.r2.boto3.client") as mock_boto:
        client = MagicMock()
        mock_boto.return_value = client
        yield client


@pytest.fixture()
def provider(mock_client):
    return R2StorageProvider(
        account_id="acct123",
        access_key_id="key",
        secret_access_key="secret",
        bucket_name="my-bucket",
    )


def test_constructor_builds_the_default_r2_endpoint(mock_client):
    with patch("app.storage.r2.boto3.client") as mock_boto:
        R2StorageProvider(
            account_id="acct123", access_key_id="k", secret_access_key="s", bucket_name="b"
        )
        _, kwargs = mock_boto.call_args
        assert kwargs["endpoint_url"] == "https://acct123.r2.cloudflarestorage.com"


def test_constructor_respects_an_explicit_endpoint_override(mock_client):
    with patch("app.storage.r2.boto3.client") as mock_boto:
        R2StorageProvider(
            account_id="acct123",
            access_key_id="k",
            secret_access_key="s",
            bucket_name="b",
            endpoint_url="https://custom.example.com",
        )
        _, kwargs = mock_boto.call_args
        assert kwargs["endpoint_url"] == "https://custom.example.com"


def test_save_calls_put_object_with_the_right_bucket_and_key(provider, mock_client):
    provider.save("owner/dataset.csv", b"a,b\n1,2\n")
    mock_client.put_object.assert_called_once_with(
        Bucket="my-bucket", Key="owner/dataset.csv", Body=b"a,b\n1,2\n"
    )


def test_open_returns_the_object_body(provider, mock_client):
    mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"hello")}
    result = provider.open("owner/x.csv")
    assert result.read() == b"hello"
    mock_client.get_object.assert_called_once_with(Bucket="my-bucket", Key="owner/x.csv")


def test_exists_true_when_head_object_succeeds(provider, mock_client):
    mock_client.head_object.return_value = {}
    assert provider.exists("owner/present.csv") is True


def test_exists_false_on_a_404_client_error(provider, mock_client):
    mock_client.head_object.side_effect = ClientError(
        {"ResponseMetadata": {"HTTPStatusCode": 404}, "Error": {"Code": "404"}}, "HeadObject"
    )
    assert provider.exists("owner/missing.csv") is False


def test_exists_reraises_a_non_404_client_error(provider, mock_client):
    mock_client.head_object.side_effect = ClientError(
        {"ResponseMetadata": {"HTTPStatusCode": 500}, "Error": {"Code": "500"}}, "HeadObject"
    )
    with pytest.raises(ClientError):
        provider.exists("owner/x.csv")


def test_delete_calls_delete_object(provider, mock_client):
    provider.delete("owner/to-delete.csv")
    mock_client.delete_object.assert_called_once_with(Bucket="my-bucket", Key="owner/to-delete.csv")


def test_local_path_downloads_to_a_temp_file_and_cleans_up(provider, mock_client):
    mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"downloaded content")}

    captured_path = None
    with provider.local_path("owner/x.csv") as path:
        captured_path = path
        assert path.read_bytes() == b"downloaded content"

    assert not captured_path.exists()  # cleaned up after the with-block
