import pytest
from pytest_mock import MockerFixture
from unittest.mock import Mock

from nldas_ingestion.infrastructure.storage.minio_object_store import MinioObjectStore
from nldas_ingestion.infrastructure.storage.protocols import StorageClient


@pytest.fixture
def storage_client_mock(mocker: MockerFixture) -> Mock:
    return mocker.Mock(spec=StorageClient)


@pytest.fixture
def minio_object_store(storage_client_mock: Mock) -> MinioObjectStore:
    return MinioObjectStore(
        client=storage_client_mock,
        bucket_name="nldas",
    )


class TestMinioObjectStore:

    class TestGet:

        def test_returns_payload_and_uses_configured_bucket(self: object,
            storage_client_mock: Mock,
            minio_object_store: MinioObjectStore
        ):
            """
            Q: What happens when the storage client successfully gets an object?
            A: The payload is returned and the configured bucket and key are delegated.
            """
            key = "path/to/object"
            expected_payload = b"object payload"
            storage_client_mock.get_object.return_value = expected_payload

            result = minio_object_store.get(key)

            assert result == expected_payload
            storage_client_mock.get_object.assert_called_once_with("nldas", key)

        def test_storage_client_errors_propagate(self: object,
            storage_client_mock: Mock,
            minio_object_store: MinioObjectStore
        ):
            """
            Q: How does the object store handle an error from get_object()?
            A: The original error propagates to the caller.
            """
            error = RuntimeError("storage unavailable")
            storage_client_mock.get_object.side_effect = error

            with pytest.raises(RuntimeError) as raised:
                minio_object_store.get("path/to/object")

            assert raised.value is error

    class TestGetStream:

        def test_returns_stream_context_and_uses_configured_bucket(self: object,
            mocker: MockerFixture,
            storage_client_mock: Mock,
            minio_object_store: MinioObjectStore
        ):
            """
            Q: What happens when the storage client successfully creates an object stream?
            A: Its context manager is returned and the configured bucket and key are delegated.
            """
            key = "path/to/object"
            expected_context = mocker.sentinel.stream_context
            storage_client_mock.get_object_stream.return_value = expected_context

            result = minio_object_store.get_stream(key)

            assert result is expected_context
            storage_client_mock.get_object_stream.assert_called_once_with(
                bucket_name="nldas",
                object_name=key,
            )

        def test_storage_client_errors_propagate(self: object,
            storage_client_mock: Mock,
            minio_object_store: MinioObjectStore
        ):
            """
            Q: How does the object store handle an error from get_object_stream()?
            A: The original error propagates to the caller.
            """
            error = RuntimeError("stream unavailable")
            storage_client_mock.get_object_stream.side_effect = error

            with pytest.raises(RuntimeError) as raised:
                minio_object_store.get_stream("path/to/object")

            assert raised.value is error

    class TestPut:

        def test_wraps_bytes_and_delegates_content_metadata(self: object,
            storage_client_mock: Mock,
            minio_object_store: MinioObjectStore
        ):
            """
            Q: What happens when bytes are successfully written to the object store?
            A: The bytes are wrapped in a stream and delegated with their length and content type.
            """
            key = "path/to/object"
            payload = b"object payload"
            content_type = "application/octet-stream"

            result = minio_object_store.put(key, payload, content_type)

            assert result is None
            storage_client_mock.put_object.assert_called_once()
            call_kwargs = storage_client_mock.put_object.call_args.kwargs
            assert call_kwargs["bucket_name"] == "nldas"
            assert call_kwargs["object_name"] == key
            assert call_kwargs["length"] == len(payload)
            assert call_kwargs["content_type"] == content_type
            assert call_kwargs["data"].read() == payload

        def test_storage_client_errors_propagate(self: object,
            storage_client_mock: Mock,
            minio_object_store: MinioObjectStore
        ):
            """
            Q: How does the object store handle an error from put_object()?
            A: The original error propagates to the caller.
            """
            error = RuntimeError("storage unavailable")
            storage_client_mock.put_object.side_effect = error

            with pytest.raises(RuntimeError) as raised:
                minio_object_store.put(
                    "path/to/object",
                    b"object payload",
                    "application/octet-stream",
                )

            assert raised.value is error

    class TestPutStream:

        def test_delegates_stream_and_explicit_length(self: object,
            storage_client_mock: Mock,
            minio_object_store: MinioObjectStore
        ):
            """
            Q: What happens when a stream is successfully written to the object store?
            A: The same stream, explicit length, and content type are delegated with the configured bucket and key.
            """
            key = "path/to/object"
            stream = Mock()
            length = 128
            content_type = "application/octet-stream"

            result = minio_object_store.put_stream(
                key,
                stream,
                length,
                content_type,
            )

            assert result is None
            storage_client_mock.put_object.assert_called_once_with(
                bucket_name="nldas",
                object_name=key,
                data=stream,
                length=length,
                content_type=content_type,
            )

        def test_storage_client_errors_propagate(self: object,
            storage_client_mock: Mock,
            minio_object_store: MinioObjectStore
        ):
            """
            Q: How does the object store handle an error from put_object() for a stream?
            A: The original error propagates to the caller.
            """
            error = RuntimeError("storage unavailable")
            storage_client_mock.put_object.side_effect = error

            with pytest.raises(RuntimeError) as raised:
                minio_object_store.put_stream(
                    "path/to/object",
                    Mock(),
                    128,
                    "application/octet-stream",
                )

            assert raised.value is error

    class TestDelete:

        def test_delegates_configured_bucket_and_key(self: object,
            storage_client_mock: Mock,
            minio_object_store: MinioObjectStore
        ):
            """
            Q: What happens when an object is successfully deleted?
            A: The configured bucket and key are delegated to the storage client.
            """
            key = "path/to/object"

            result = minio_object_store.delete(key)

            assert result is None
            storage_client_mock.remove_object.assert_called_once_with("nldas", key)

        def test_storage_client_errors_propagate(self: object,
            storage_client_mock: Mock,
            minio_object_store: MinioObjectStore
        ):
            """
            Q: How does the object store handle an error from remove_object()?
            A: The original error propagates to the caller.
            """
            error = RuntimeError("storage unavailable")
            storage_client_mock.remove_object.side_effect = error

            with pytest.raises(RuntimeError) as raised:
                minio_object_store.delete("path/to/object")

            assert raised.value is error