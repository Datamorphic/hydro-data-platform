# If we authenticate for every time an nldas client is created and used
# will this add unnecessary networking calls to saving that token and passing it
# around from program calls.
# Does earthaccess know how to cache tokens?

class NLDASClient:

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