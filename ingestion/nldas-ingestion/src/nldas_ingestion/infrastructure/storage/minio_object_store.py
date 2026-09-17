from io import BytesIO
from typing import BinaryIO
from contextlib import AbstractContextManager

from nldas_ingestion.infrastructure.storage.protocols import StorageClient

class MinioObjectStore:
    """
    A.K.A. Infrastructure storage adapter or gateway
    Exposes storage operations to the application while hiding MinIO-specific details.
    """

    def __init__(self, client: StorageClient, bucket_name: str) -> None:
        self._client = client
        self._bucket_name = bucket_name

    def get(self, key: str) -> bytes:
        """
        Input:
            `Key`: the object identifer/name used by the client.
                For S3 protocol systems, this is looks like a
                relative path from the `bucket_name`. Use discovery 
                services for the object storage service to determine the
                object resource location (key / object name)<br>

        `Example`:<br>
            **bucket_name**: nldas
            **key**: credentials/earthdata/token.json<br>
            This points to ***nldas/credentials/earthdata/token.json***
    

        """
        return self._client.get_object(
            self._bucket_name,
            key
        )

    def get_stream(self, key: str) -> AbstractContextManager[BinaryIO]:
        return self._client.get_object_stream(
            bucket_name=self._bucket_name,
            object_name=key
        )

    def put(self, 
            key: str, 
            data: bytes, 
            content_type: str
        ) -> None:
        """Writes `data [bytes]` to object storage in object store bucket as `key`.
        
        Inputs:
            `content_type`: The type of content to be stored.
        """
        self._client.put_object(
            bucket_name=self._bucket_name,
            object_name=key,
            data=BytesIO(data),
            length=len(data),
            content_type=content_type
        )

    def put_stream(self, 
            key: str, 
            data: BinaryIO, 
            length: int,
            content_type: str
        ) -> None:
        """Writes `data stream [BinaryIO]` to object storage in object store bucket as `key`."""
        self._client.put_object(
            bucket_name=self._bucket_name,
            object_name=key,
            data=data,
            length=length,
            content_type=content_type
        )

    def delete(self, key: str) -> None:
        """Deletes `key` from object storage in object store bucket."""
        self._client.remove_object(
            self._bucket_name,
            key
        )

if __name__ == "__main__":

    # example composition
    from nldas_ingestion.infrastructure.storage.minio_storage_client import MinioStorageClient

    client = MinioStorageClient(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
    )

    payload = b'these are some bytes'

    object_store = MinioObjectStore(
        client=client,
        bucket_name="nldas"
    )

    object_store.put(
        key="partition1/object1.json",
        data=payload,
        content_type="application/json"
    )

