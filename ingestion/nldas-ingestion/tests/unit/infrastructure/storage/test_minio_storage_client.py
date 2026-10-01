import pytest
from pytest_mock import MockerFixture
from unittest.mock import Mock

import nldas_ingestion.infrastructure.storage.minio_storage_client as msc 
import nldas_ingestion.infrastructure.storage.exceptions as StorageError
from minio import S3Error


@pytest.fixture
def minio_client(mocker: MockerFixture) -> Mock:
    return mocker.Mock(spec=msc.Minio)

@pytest.fixture
def storage_client(
    monkeypatch: pytest.MonkeyPatch,
    minio_client: Mock
) -> msc.MinioStorageClient:
    
    endpoint='endpoint'
    access_key='access_key'
    secret_key='secret_key'
    minio_client.endpoint = endpoint
    minio_client.access_key = access_key
    minio_client.secret_key = secret_key

    monkeypatch.setattr(msc, "Minio", lambda **kwargs: minio_client)

    return msc.MinioStorageClient(
        endpoint='endpoint',
        access_key='access_key',
        secret_key='secret_key'
    )

def create_s3_error(s3_error_code: str) -> S3Error:
    return S3Error(
        response=Mock(),
        code=s3_error_code,
        message=None,
        resource=None,
        request_id=None,
        host_id=None,
        bucket_name=None,
        object_name=None
    )


class TestMinioStorageClient:


    class TestGetObject:

        def test_valid_minio_client_response_returns_payload_and_deconstructs(self,
            mocker: MockerFixture,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient        
        ):
            """
            Q: What happens if the Minio client returns a valid response?
            A: The byte payload is returned and the response deconstructs.
            """
            expected_result = b'payload'
            bucket_name = 'bucket_name'
            object_name = 'object_name'
            mock_response: Mock = mocker.Mock()
            mock_response.read.return_value = expected_result 
            minio_client.get_object.return_value = mock_response

            result = storage_client.get_object(
                bucket_name=bucket_name,
                object_name=object_name
            )

            assert isinstance(result, bytes)
            assert result == expected_result
            minio_client.get_object.assert_called_once_with(
                bucket_name=bucket_name,
                object_name=object_name
            )
            mock_response.read.assert_called_once()
            mock_response.close.assert_called_once()
            mock_response.release_conn.assert_called_once()
            

        def test_minio_client_s3_errors_translate_to_storage_errors(self,
            minio_client: Mock, 
            storage_client: msc.MinioStorageClient
        ):
            """
            Q: How are Minio S3Errors produced by ._mio.get_object() handled?
            A: They should be translated to application storage errors.
            """
            
            bucket_name = 'bucket_name'
            object_name = 'object_name'
            minio_client.get_object.side_effect = S3Error

            with pytest.raises(StorageError.StorageError):
                storage_client.get_object(
                    bucket_name=bucket_name,
                    object_name=object_name
                )

            minio_client.get_object.assert_called_once_with(
                bucket_name=bucket_name,
                object_name=object_name
            )

        def test_minio_client_non_s3_errors_raise_storage_service_error(self,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient
        ):
            """
            Q: How are non S3Errors produced by ._mio.get_object handled?
            A: They should raise a StorageServiceError
            """
            bucket_name = 'bucket_name'
            object_name = 'object_name'
            NonS3Error = RuntimeError
            minio_client.get_object.side_effect = NonS3Error

            with pytest.raises(StorageError.StorageServiceError):
                storage_client.get_object(
                    bucket_name=bucket_name,
                    object_name=object_name
                )

            minio_client.get_object.assert_called_once_with(
                bucket_name=bucket_name,
                object_name=object_name
            )

        def test_corrupt_minio_client_response_raises_storage_service_error_and_deconstructs(self,
            mocker: MockerFixture,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient        
        ):
            """
            Q: How are unexpected exceptions raised caused reading the minio client response handled?
            A: They should be caught and translated into a storage service error.
            """
            bucket_name = 'bucket_name'
            object_name = 'object_name'
            ResponseReadError = RuntimeError
            mock_response: Mock = mocker.Mock()
            mock_response.read.side_effect = ResponseReadError
            minio_client.get_object.return_value = mock_response

            with pytest.raises(StorageError.StorageServiceError):
                storage_client.get_object(
                    bucket_name=bucket_name,
                    object_name=object_name
                )

            minio_client.get_object.assert_called_once_with(
                bucket_name=bucket_name,
                object_name=object_name
            )
            mock_response.read.assert_called_once()
            mock_response.close.assert_called_once()
            mock_response.release_conn.assert_called_once()


    class TestPutObject:
        def test_valid_minio_client_response_returns_object_put_response(self,
            mocker: MockerFixture,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient
        ):
            """
            Q: What happens when the MinIO client successfully puts an object?
            A: An ObjectPutResponse is returned with the object metadata.
            """
            bucket_name = "bucket_name"
            object_name = "object_name"
            content_type = "application/octet-stream"
            data = Mock()
            length = 7
            etag = "etag-value"
            minio_result = mocker.Mock(
                object_name=object_name,
                bucket_name=bucket_name,
                etag=etag,
            )
            minio_client.put_object.return_value = minio_result

            result = storage_client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=data,
                length=length,
                content_type=content_type,
            )

            assert isinstance(result, msc.MinioObjectPutResponse)
            assert result.object_name == object_name
            assert result.bucket_name == bucket_name
            assert result.content_type == content_type
            assert result.etag == etag
            minio_client.put_object.assert_called_once_with(
                bucket_name=bucket_name,
                object_name=object_name,
                data=data,
                length=length,
                content_type=content_type,
            )

        def test_minio_client_s3_errors_translate_to_storage_errors(self,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient
        ):
            """
            Q: How are S3Errors produced by ._mio.put_object() handled?
            A: They are translated to application storage errors.
            """
            s3_error = create_s3_error("InvalidBucketName")
            minio_client.put_object.side_effect = s3_error
            data = Mock()

            with pytest.raises(StorageError.StorageRequestError) as raised:
                storage_client.put_object(
                    bucket_name="bucket_name",
                    object_name="object_name",
                    data=data,
                    length=7,
                    content_type="application/octet-stream",
                )

            assert raised.value.__cause__ is s3_error
            minio_client.put_object.assert_called_once_with(
                bucket_name="bucket_name",
                object_name="object_name",
                data=data,
                length=7,
                content_type="application/octet-stream",
            )

        def test_minio_client_non_s3_errors_raise_storage_service_error(self,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient
        ):
            """
            Q: How are non-S3 errors produced by ._mio.put_object() handled?
            A: They raise a StorageServiceError.
            """
            minio_client.put_object.side_effect = RuntimeError("connection failed")
            data = Mock()

            with pytest.raises(StorageError.StorageServiceError):
                storage_client.put_object(
                    bucket_name="bucket_name",
                    object_name="object_name",
                    data=data,
                    length=7,
                    content_type="application/octet-stream",
                )

            minio_client.put_object.assert_called_once_with(
                bucket_name="bucket_name",
                object_name="object_name",
                data=data,
                length=7,
                content_type="application/octet-stream",
            )


    class TestRemoveObject:
        def test_successful_minio_client_call_returns_none(self,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient
        ):
            """
            Q: What happens when the MinIO client successfully removes an object?
            A: The object is removed and the method returns None.
            """
            bucket_name = "bucket_name"
            object_name = "object_name"

            result = storage_client.remove_object(
                bucket_name=bucket_name,
                object_name=object_name,
            )

            assert result is None
            minio_client.remove_object.assert_called_once_with(
                bucket_name=bucket_name,
                object_name=object_name,
            )

        def test_minio_client_s3_errors_translate_to_storage_errors(self,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient
        ):
            """
            Q: How are S3Errors produced by ._mio.remove_object() handled?
            A: They are translated to application storage errors.
            """
            s3_error = create_s3_error("NoSuchKey")
            minio_client.remove_object.side_effect = s3_error

            with pytest.raises(StorageError.StorageObjectMissingError) as raised:
                storage_client.remove_object(
                    bucket_name="bucket_name",
                    object_name="object_name",
                )

            assert raised.value.__cause__ is s3_error
            minio_client.remove_object.assert_called_once_with(
                bucket_name="bucket_name",
                object_name="object_name",
            )

        def test_minio_client_non_s3_errors_raise_storage_service_error(self,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient
        ):
            """
            Q: How are non-S3 errors produced by ._mio.remove_object() handled?
            A: They raise a StorageServiceError.
            """
            minio_client.remove_object.side_effect = RuntimeError("connection failed")

            with pytest.raises(StorageError.StorageServiceError):
                storage_client.remove_object(
                    bucket_name="bucket_name",
                    object_name="object_name",
                )

            minio_client.remove_object.assert_called_once_with(
                bucket_name="bucket_name",
                object_name="object_name",
            )


class TestMinioObjectStreamContext:
    """
    __enter__ runs when execution reaches with context as value; 
        its return value becomes value. Here, it calls `MinIO` `get_object()` 
        and returns that response. `__exit__` runs when the with block finishes, 
        whether normally or due to an exception. It closes the response and 
        releases the connection; returning None means exceptions from the block 
        are not suppressed.
    """


    class TestEnter:

        def test_returns_response_and_closes_it_when_context_exits(
            self,
            mocker: MockerFixture,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient,
        ):
            """Entering yields the MinIO response; exiting releases it."""
            bucket_name = "bucket_name"
            object_name = "object_name"
            mock_response = mocker.Mock()
            minio_client.get_object.return_value = mock_response
            stream_context = storage_client.get_object_stream(
                bucket_name=bucket_name,
                object_name=object_name,
            )

            with stream_context as stream:
                assert stream is mock_response

            minio_client.get_object.assert_called_once_with(
                bucket_name=bucket_name,
                object_name=object_name,
            )
            mock_response.close.assert_called_once_with()
            mock_response.release_conn.assert_called_once_with()

        def test_minio_client_s3_errors_translate_to_storage_errors(self,
            minio_client: Mock, 
            storage_client: msc.MinioStorageClient
        ):
            """
            Q: How are Minio S3Errors produced by ._client.get_object() handled?
            A: They should be translated to application storage errors.
            """
            s3_error = create_s3_error("NoSuchKey")
            minio_client.get_object.side_effect = s3_error

            with pytest.raises(StorageError.StorageObjectMissingError) as raised:
                with storage_client.get_object_stream(
                    bucket_name="bucket_name",
                    object_name="object_name",
                ):
                    pytest.fail("Context body should not run when __enter__ fails")

            assert raised.value.__cause__ is s3_error
            minio_client.get_object.assert_called_once_with(
                bucket_name="bucket_name",
                object_name="object_name",
            )

        def test_minio_client_non_s3_errors_raise_storage_service_error(self,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient
        ):
            """
            Q: How are non S3Errors produced by ._mio.get_object handled?
            A: They should raise a StorageServiceError
            """
            minio_client.get_object.side_effect = RuntimeError("connection failed")

            with pytest.raises(StorageError.StorageServiceError):
                with storage_client.get_object_stream(
                    bucket_name="bucket_name",
                    object_name="object_name",
                ):
                    pytest.fail("Context body should not run when __enter__ fails")

            minio_client.get_object.assert_called_once_with(
                bucket_name="bucket_name",
                object_name="object_name",
            )


    class TestExit:

        def test_body_exception_propagates_after_response_cleanup(
            self,
            mocker: MockerFixture,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient,
        ):
            mock_response = mocker.Mock()
            minio_client.get_object.return_value = mock_response

            with pytest.raises(RuntimeError, match="body failed"):
                with storage_client.get_object_stream(
                    bucket_name="bucket_name",
                    object_name="object_name",
                ):
                    raise RuntimeError("body failed")

            mock_response.close.assert_called_once_with()
            mock_response.release_conn.assert_called_once_with()

        def test_exit_without_enter_is_a_no_op(
            self,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient,
        ):
            stream_context = storage_client.get_object_stream(
                bucket_name="bucket_name",
                object_name="object_name",
            )

            assert stream_context.__exit__(None, None, None) is None
            minio_client.get_object.assert_not_called()

        def test_release_conn_runs_if_close_raises(
            self,
            mocker: MockerFixture,
            minio_client: Mock,
            storage_client: msc.MinioStorageClient,
        ):
            mock_response = mocker.Mock()
            mock_response.close.side_effect = RuntimeError("close failed")
            minio_client.get_object.return_value = mock_response
            stream_context = storage_client.get_object_stream(
                bucket_name="bucket_name",
                object_name="object_name",
            )
            stream_context.__enter__()

            with pytest.raises(RuntimeError, match="close failed"):
                stream_context.__exit__(None, None, None)

            mock_response.close.assert_called_once_with()
            mock_response.release_conn.assert_called_once_with()


class TestRaiseTranslatedMinioS3Error:

    @pytest.mark.parametrize(
        ("s3_error_code", "storage_error"),
        [
            ("NoSuchKey",StorageError.StorageObjectMissingError), 
            ("NoSuchObject",StorageError.StorageObjectMissingError), 
            ("AccessDenied",StorageError.StoragePermissionError),
            ("InvalidAccessKeyId",StorageError.StoragePermissionError),
            ("SignatureDoesNotMatch",StorageError.StoragePermissionError),
            ("InvalidToken",StorageError.StoragePermissionError),
            ("ExpiredToken",StorageError.StoragePermissionError),
            ("NoSuchBucket",StorageError.StorageObjectMissingError),
            ("InternalError",StorageError.StorageUnavailableError),
            ("ServiceUnavailable",StorageError.StorageUnavailableError),
            ("SlowDown",StorageError.StorageUnavailableError),
            ("RequestTimeout",StorageError.StorageUnavailableError),
            ("InvalidBucketName",StorageError.StorageRequestError),
            ("InvalidArgument",StorageError.StorageRequestError),
            ("InvalidRequest",StorageError.StorageRequestError),
            ("EntityTooSmall",StorageError.StorageRequestError),
            ("EntityTooLarge",StorageError.StorageRequestError),
            ("MalformedXML",StorageError.StorageRequestError),
            ("InvalidDigest",StorageError.StorageRequestError),
            ("Unknown", StorageError.StorageServiceError)
        ]
    )
    def test_minio_s3_errors_translate_to_storage_errors(self, 
            s3_error_code: str,
            storage_error: type[StorageError.StorageError]
        ):

        s3_error: S3Error = create_s3_error(s3_error_code)

        with pytest.raises(storage_error):
            msc.raise_translated_minio_s3_error(
                s3_error=s3_error,
                bucket_name='bucket_name',
                object_name='object_name'
            )
        