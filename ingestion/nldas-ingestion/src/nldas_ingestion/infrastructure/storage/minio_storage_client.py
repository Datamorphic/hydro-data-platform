from dataclasses import dataclass
from typing import (BinaryIO, cast, Dict, List, Tuple, NoReturn)
from contextlib import AbstractContextManager
from minio import Minio
from minio.error import S3Error
from minio.helpers import ObjectWriteResult
# import io # io.BytesIO(bytes) -> BytesIO class which passes BinaryIO protocol class
from nldas_ingestion.infrastructure.storage.protocols import ObjectPutResponse
import nldas_ingestion.infrastructure.storage.exceptions as err

class MinioStorageClient:

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
    ):
        self._mio = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False
        )

    def get_object(
        self, 
        bucket_name: str, 
        object_name: str
    ) -> bytes:

        try:
            response = self._mio.get_object(
                bucket_name = bucket_name,
                object_name = object_name
            )
        except S3Error as exc:
            raise_translated_minio_s3_error(
                s3_error=exc,
                bucket_name=bucket_name,
                object_name=object_name
            )
        except Exception as exc:
            raise err.StorageServiceError(
                f"Minio storage client failed unexpectedly while getting object {bucket_name}/{object_name}."
            )
            
        try:
            return response.read() # extract bytes to memory as opposed to maintaining stream
        except Exception as error:
            raise err.StorageServiceError(
                f"Minio storage client failed unexpectedly while reading object {bucket_name}/{object_name}"
            ) from error
        finally: # happens after try or exception block (return result is held)
            response.close()
            response.release_conn()

    def get_object_stream(
        self,
        bucket_name: str,
        object_name: str
    ) -> AbstractContextManager[BinaryIO]:
        """Returns a context manager that produces a BinarIO object
        ***Best used with a `with` code block***
        """
        response = MinioObjectStreamContext(
            client=self._mio,
            bucket_name=bucket_name,
            object_name=object_name
        )
        return response

    def put_object(
        self, 
        bucket_name: str, 
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str,
        **kwargs
    ) -> ObjectPutResponse:
        """
        Uploads data to object storage and returns an object put response.
        """
        try:
            result: ObjectWriteResult = (
                self._mio
                .put_object(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    data=data,
                    length=length,
                    content_type=content_type
            ))
        except S3Error as exc:
            raise_translated_minio_s3_error(
                s3_error=exc,
                bucket_name=bucket_name,
                object_name=object_name
            )
        except Exception as exc:
            raise err.StorageServiceError(
                f"Minio storage client failed unexpectedly while putting object {bucket_name}/{object_name}."
            )

        return MinioObjectPutResponse(
            object_name=result.object_name,
            bucket_name=result.bucket_name,
            content_type=content_type,
            etag=result.etag
        )

    def remove_object(
        self,
        bucket_name: str,
        object_name: str
    ) -> None:

        try:
            self._mio.remove_object(
                bucket_name=bucket_name,
                object_name=object_name
            )
        except S3Error as exc:
            raise_translated_minio_s3_error(
                s3_error=exc,
                bucket_name=bucket_name,
                object_name=object_name
            )
        except Exception as exc:
            raise err.StorageServiceError(
                f"Minio storage client failed unexpectedly while deleting object {bucket_name}/{object_name}."
            )


def raise_translated_minio_s3_error(
    s3_error: S3Error,
    bucket_name: str,
    object_name: str,
) -> NoReturn:
    """
    Translates the `minio.error.S3Error` using domain logic to produce the following ***Exceptions***:
        `StorageObjectMissingError`: When the object is missing from storage.<br>
        `StoragePermissionError`: When the credentials lack permission for the storage operation.<br>
        `StorageBucketMissingError`: When the specified `bucket_name` does not exist in the storage server.<br>
        `StorageUnavailableError`: When storage service cannot currently be reached or is offline.<br>
    """

    if s3_error.code in {"NoSuchKey", "NoSuchObject"}:
        raise err.StorageObjectMissingError(
            f"Object does not exist: {bucket_name}/{object_name}"
        ) from s3_error

    if s3_error.code in {
        "AccessDenied",
        "InvalidAccessKeyId",
        "SignatureDoesNotMatch",
        "InvalidToken",
        "ExpiredToken",
    }:
        raise err.StoragePermissionError(
            "Object storage rejected the configured credentials."
        ) from s3_error

    if s3_error.code == "NoSuchBucket":
        raise err.StorageObjectMissingError(
            f"Bucket does not exist: {bucket_name}"
        ) from s3_error

    if s3_error.code in {
        "InternalError",
        "ServiceUnavailable",
        "SlowDown",
        "RequestTimeout",
    }:
        raise err.StorageUnavailableError(
            "Object storage returned a temporary service error."
        ) from s3_error

    if s3_error.code in {
        "InvalidBucketName",
        "InvalidArgument",
        "InvalidRequest",
        "EntityTooSmall",
        "EntityTooLarge",
        "MalformedXML",
        "InvalidDigest",
    }:
        raise err.StorageRequestError(
            f"Object storage rejected the request for {bucket_name}/{object_name}."
        ) from s3_error

    raise err.StorageServiceError(
        f"Object storage returned an unclassified S3 error for "
        f"{bucket_name}/{object_name}: {s3_error.code}"
    ) from s3_error


@dataclass
class MinioObjectPutResponse:
    object_name: str
    bucket_name: str
    content_type: str
    etag: str | None


class MinioObjectStreamContext():
    """Context manager for the HTTPResponse object [BinarIO]
    produced by minIO.get_object(...)
    """
    def __init__(
        self,
        client: Minio,
        bucket_name: str,
        object_name: str
    ):
        self._client = client
        self._bucket_name = bucket_name
        self._object_name = object_name
        self._response = None

    def __enter__(self) -> BinaryIO:

        try:
            self._response = (
                self._client
                .get_object(
                    bucket_name=self._bucket_name,
                    object_name=self._object_name
                )
            )
        except S3Error as exc:
            raise_translated_minio_s3_error(
                s3_error=exc,
                bucket_name=self._bucket_name,
                object_name=self._object_name
            )
        except Exception as exc:
            raise err.StorageServiceError(
                f"Object storage rejected the request for {self._bucket_name}/{self._object_name}."
            )
                
        # MinIO's response is stream-like, but its SDK type may not be
        # declared as BinaryIO. The cast only informs the type checker.
        return cast(BinaryIO, self._response)

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: object | None
    ) -> None:
        if self._response is None:
            return
        try:
            self._response.close()
        finally:
            self._response.release_conn()

        self._response = None

if __name__ == "__main__":
    # MinIO client testing

    # MinIO SDK testing
    client = Minio(
        endpoint="10.0.0.41:9000",
        access_key="minioadmin",
        secret_key="D@t@2Knowledge",
        secure=False
    )

    # Make the bucket if it doesn't exist.
    bucket_name = "raw"
    found = client.bucket_exists(bucket_name)
    if not found:
        try:
            client.make_bucket(bucket_name)
            print("Created bucket", bucket_name)
        except Exception as e:
            raise RuntimeError("Failed .make_bucket(...)") from e
    else:
        print("Bucket", bucket_name, "already exists")

    # Create an dictionary to represent content of json file
    import json
    import io
    json_content = {
        "type": "token",
        "access_token": "hca1234xyalfs2"
    }

    # serialize -> bytes -> bytestream
    json_content_serialized = json.dumps(json_content)
    json_content_bytes = bytes(json_content_serialized, encoding="utf-8")
    json_content_stream = io.BytesIO(json_content_bytes)

    # meta-data
    metadata: Dict[str, str | List[str] | Tuple[str]] = {
        "type": "json",
        "name": "test",
        "partition_a": "taga1",
        "partition_b": "tagb1"
    }
    # upload data to the object store
    try:
        result = client.put_object(
            bucket_name=bucket_name,
            object_name="taga1/tagb1/test.json",
            data=json_content_stream,
            length=len(json_content_bytes),
            content_type="application/json",
            metadata=metadata
        )
        print(
            "created {0} object; etag: {1}, version-id: {2}".format(
                result.object_name, result.etag, result.version_id)
        )
    except Exception as e:
        raise RuntimeError("Failed .put_object(...)") from e

    
