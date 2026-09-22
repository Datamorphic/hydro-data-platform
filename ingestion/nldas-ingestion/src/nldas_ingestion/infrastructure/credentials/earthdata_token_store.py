from pathlib import Path
import json

from nldas_ingestion.infrastructure.storage.protocols import (ObjectStore)
import nldas_ingestion.infrastructure.credentials.exceptions as CredentialErrors
import nldas_ingestion.infrastructure.storage.exceptions as StorageErrors

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

    def get_token(self) -> str: # TODO: Update error handling to handle custom errors and translate accordingly
        try:
            token_data = self._object_store.get(self._object_key)

        except StorageErrors.StorageObjectMissingError as exc:
            raise CredentialErrors.TokenCacheMissingError(
                "Token cache missing"
            ) from exc
        except StorageErrors.StoragePermissionError as exc:
            raise CredentialErrors.TokenConfigurationError(
                "Object store credentials are invalid"
            ) from exc
        except StorageErrors.StorageUnavailableError as exc:
            raise CredentialErrors.TokenServiceUnavailableError(
                "Object store unavailable"
            ) from exc
        except StorageErrors.StorageRequestError as exc:
            raise CredentialErrors.TokenConfigurationError(
                "Invalid request sent to object store"
            )
        except StorageErrors.StorageServiceError as exc:
            raise CredentialErrors.TokenServiceUnavailableError(
                "Object store failed failed unexpectedly"
            )
        
        token_dict: dict = json.loads(token_data.decode("utf-8"))
        token: str | None = token_dict.get("access_token")
        if not token:
            raise CredentialErrors.TokenCacheMissingError(
                "Token is missing from cache"
            )
        return token

    def put_token(self, token: str) -> None:
        
        token_data = json.dumps({
            "token_type": "Bearer",
            "access_token": token
        })

        try:
            self._object_store.put(
                key=self._object_key,
                data=token_data.encode("utf-8"),
                content_type="application/json"
            )
        except StorageErrors.StorageObjectMissingError as exc:
            raise CredentialErrors.TokenConfigurationError(
                f"Token cache bucket does not exist in object store."
            )
        except StorageErrors.StoragePermissionError as exc:
            raise CredentialErrors.TokenConfigurationError(
                "Object store credentials are invalid."
            )
        except StorageErrors.StorageRequestError as exc:
            raise CredentialErrors.TokenConfigurationError(
                 "Invalid request sent to object store"
            )
        except StorageErrors.StorageUnavailableError as exc:
            raise CredentialErrors.TokenServiceUnavailableError(
                "Object store is unavailable or offline."
            )
        except StorageErrors.StorageServiceError as exc:
            raise CredentialErrors.TokenServiceUnavailableError(
                "Object store failed unexpectedly."
            )
        