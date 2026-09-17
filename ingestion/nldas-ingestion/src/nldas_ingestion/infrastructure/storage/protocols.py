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
        """For small objects such as tokens."""
        ...

    def get_stream(self, key: str) -> AbstractContextManager[BinaryIO]:
        """For large objects such as NetCDF files."""
        ...

    def put(self, key: str, data: bytes) -> None: # what is the return type (probably none or a task or resource identifier).
        """For small objects."""
        ...

    def put_stream(self, key: str, data: BinaryIO, length: int) -> None:
        """For large or already-streamed objects."""
        ...

    def delete(self, key: str) -> None: # any return type, probably not except for a task or resource identifier
        ...

