"""
Client for interfacing with NASA ???? server(s). Storage servers other than GES DISC (Earth Data?)
- Uses EarthAccess library abstraction as nested client.
"""

# If we authenticate for every time an nldas client is created and used
# will this add unnecessary networking calls to saving that token and passing it
# around from program calls.
# Does earthaccess know how to cache tokens?
from typing import Protocol

class CredentialProvider(Protocol):
    ...

class NLDASClient:
    """
    A.K.A. Infrastructure adapter or external service gateway
    Purpose is to serve as a communication intermediary between a caller and an external service
        to request information/service.

    Performs external service requests and returns the resulting data or operation outcome to the application service.
    """
    def __init__(self, credential_provider: CredentialProvider):
        self._credential_provider = credential_provider

    def authenticate(self):
        '''Authenticates a user with earthaccess credentials and stores token for subsequent nework requests'''
        ...

    def search_granules(self):
        '''Searches the NASA CRM catalog for NLDAS granules based on specified constraints'''
        ...

    def download_granule(self):
        '''Downloads a full granule from NASAs servers.'''
        ...

    def download_subset_granule(self):
        '''Downloads a spatial subset of the requested granule using NASA GES DISC Subsetter API.'''
        ...