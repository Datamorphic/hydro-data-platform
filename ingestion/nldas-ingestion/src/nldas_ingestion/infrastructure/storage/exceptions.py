from minio.error import S3Error

class StorageError(RuntimeError):
    """Base class for object-storage failures."""


class StorageObjectMissingError(StorageError):
    """The requested object does not exist."""


class StoragePermissionError(StorageError):
    """The credentials lack permission for the operation."""


class StorageUnavailableError(StorageError):
    """The storage service cannot currently be reached."""


class StorageRequestError(StorageError):
    """The storage request was invalid or could not be fulfilled as requested."""


class StorageServiceError(StorageError):
    """The storage service returned an unclassified error."""
