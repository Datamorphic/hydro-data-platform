from typing import Protocol, BinaryIO
from contextlib import AbstractContextManager
from dataclasses import dataclass


class ObjectPutResponse(Protocol):
    object_name: str
    bucket_name: str
    content_type: str
    etag: str | None


class StorageClient(Protocol):
    """Low-level MinIO/S3-compatible client."""

    def get_object(
        self, 
        bucket_name: str, 
        object_name: str
    ) -> bytes:
        ...

    def get_object_stream(
        self,
        bucket_name: str,
        object_name: str
    ) -> AbstractContextManager[BinaryIO]:
        ...

    def put_object(
        self, 
        bucket_name: str, 
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str
        
    ) -> ObjectPutResponse:
        ...

    def remove_object(
        self,
        bucket_name: str,
        object_name: str
    ) -> None:
        ...


class ObjectStore(Protocol):

    def get(self, key: str) -> bytes: # what is the return type? Does it depend on the object type?
        """For small objects such as tokens.
        
        Exceptions:
            `StorageObjectMissingError`: when the requested object or its bucket does not exist.
            `StoragePermissionError`: when the credentials lack permission for the operation.
            `StorageUnavailableError`: when the storage service cannot currently be reached.
            `StorageRequestError`: when the storage request was invalid or could not be fulfilled as requested.
            `StorageServiceError`: when the storage service returned an unclassified error.
        """
        ...

    def get_stream(self, key: str) -> AbstractContextManager[BinaryIO]:
        """For large objects such as NetCDF files.
        
        Exceptions:
            `StorageObjectMissingError`: when the requested object or its bucket does not exist.
            `StoragePermissionError`: when the credentials lack permission for the operation.
            `StorageUnavailableError`: when the storage service cannot currently be reached.
            `StorageRequestError`: when the storage request was invalid or could not be fulfilled as requested.
            `StorageServiceError`: when the storage service returned an unclassified error.
        """
        ...

    def put(self, key: str, data: bytes, content_type: str) -> None: # what is the return type (probably none or a task or resource identifier).
        """Operation for writting small objects.

        Exceptions:            
            `StorageObjectMissingError`: when the configured bucket/container does not exist.
            `StoragePermissionError`: when the credentials lack permission for the operation.
            `StorageUnavailableError`: when the storage service cannot currently be reached.
            `StorageRequestError`: when the storage request was invalid or could not be fulfilled as requested.
            `StorageServiceError`: when the storage service returned an unclassified error.
        """
        ...

    def put_stream(self, key: str, data: BinaryIO, length: int, content_type: str) -> None:
        """Operation for writting large or already-streamed objects.

        Exceptions:            
            `StorageObjectMissingError`: when the configured bucket/container does not exist.
            `StoragePermissionError`: when the credentials lack permission for the operation.
            `StorageUnavailableError`: when the storage service cannot currently be reached.
            `StorageRequestError`: when the storage request was invalid or could not be fulfilled as requested.
            `StorageServiceError`: when the storage service returned an unclassified error.
        """
        ...

    def delete(self, key: str) -> None: # any return type, probably not except for a task or resource identifier
        """Operation for deleting objects from storage.
        
        Exceptions:            
            `StorageObjectMissingError`: when the configured bucket/container or object does not exist.
            `StoragePermissionError`: when the credentials lack permission for the operation.
            `StorageUnavailableError`: when the storage service cannot currently be reached.
            `StorageRequestError`: when the storage request was invalid or could not be fulfilled as requested.
            `StorageServiceError`: when the storage service returned an unclassified error.
        """
        ...

