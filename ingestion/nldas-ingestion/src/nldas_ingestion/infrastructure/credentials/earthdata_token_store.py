from pathlib import Path

from nldas_ingestion.infrastructure.storage.protocols import (ObjectStore)

class EarthDataTokenStore:
    """
    Object Storage abstraction using AWS S3 Object Storage Protocol.
    Initial use-case is using MinIO object storage (uses S3 protocol)

    Inputs:
        `object_store`: generic binary-object persistence<br>
        `object_key`: token-specific<br>
    """

    def __init__(self, object_store: ObjectStore, object_key: str):
        self._object_store = object_store
        self._object_key = object_key

    def get_token(self) -> str:
        token = self._object_store.get(self._object_key)
        return token.decode("utf-8")

    def put_token(self, token: str) -> None:
        self._object_store.put(
            self._object_key,
            token.encode("utf-8")
        )